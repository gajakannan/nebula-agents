// Symbol-layer extractor for C#. Invoked by scripts/kg/symbols.py.
// Reads a JSON array of repo-relative file paths from stdin (the bound-files
// list — emission scope), parses them with Roslyn into a single
// CSharpCompilation, and emits a JSON array of symbol records to stdout.
// Each method/property/constructor record carries:
//
//   calls       — resolved {name, container} for invocations whose target
//                 symbol the semantic model can determine. Falls back to
//                 {name, container: null} when the target is external
//                 (framework/EF/etc.) or otherwise unresolved.
//   implements  — {name, container} for every interface member this method
//                 satisfies. Lets symbols.py grow polymorphic-dispatch groups
//                 so reaching an interface member reaches its implementations.
//   line, end_line — 1-based start and end lines of the declaration span;
//                 consumed by diff-impact.py to map changed hunks to symbols.
//
// CLI args:
//   --compilation-root <dir>   widens the parse scope. Each root is walked
//                              recursively for *.cs (bin/obj/node_modules
//                              skipped); discovered files join the
//                              compilation but symbols are emitted only for
//                              files present in stdin (the bound set).
//                              Repeatable; comma-separated also accepted.
//                              Default: none — compilation = stdin only,
//                              preserving prior behavior.
//   --sidecar <path>           write {source_file, source_line, target} JSON
//                              for every invocation in an UNBOUND file that
//                              resolves to a symbol declared in a BOUND
//                              file. Consumed by symbols.py to build
//                              unbound-but-referenced.yaml. When omitted,
//                              no sidecar is written.
//
// The compilation is built without metadata references — we only care about
// resolving calls between application source symbols. Framework calls are
// expected to be unresolved (container: null) and are ignored by the
// reachability walk.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Text;

namespace CSharpSymbols;

public sealed record CallRef(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("container")] string? Container
);

public sealed record SymbolItem(
    [property: JsonPropertyName("file")] string File,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("container")] string? Container,
    [property: JsonPropertyName("kind")] string Kind,
    [property: JsonPropertyName("line")] int Line,
    [property: JsonPropertyName("end_line")] int EndLine,
    [property: JsonPropertyName("signature")] string Signature,
    [property: JsonPropertyName("visibility")] string Visibility,
    [property: JsonPropertyName("calls")] CallRef[] Calls,
    [property: JsonPropertyName("implements")] CallRef[] Implements,
    [property: JsonPropertyName("instantiates")] CallRef[] Instantiates,
    [property: JsonPropertyName("type_refs")] CallRef[] TypeRefs
);

public sealed record SidecarTarget(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("container")] string? Container
);

public sealed record SidecarEntry(
    [property: JsonPropertyName("source_file")] string SourceFile,
    [property: JsonPropertyName("source_line")] int SourceLine,
    [property: JsonPropertyName("target")] SidecarTarget Target
);

public static class Program
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
        WriteIndented = false,
    };

    public static int Main(string[] args)
    {
        try { return Run(args); }
        catch (Exception ex)
        {
            Console.Error.WriteLine("extractor crashed: " + ex);
            return 1;
        }
    }

    private static int Run(string[] args)
    {
        var compilationRoots = new List<string>();
        string? sidecarPath = null;
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--compilation-root" && i + 1 < args.Length)
            {
                foreach (var part in args[++i].Split(','))
                {
                    var trimmed = part.Trim();
                    if (trimmed.Length > 0) compilationRoots.Add(trimmed);
                }
            }
            else if (args[i] == "--sidecar" && i + 1 < args.Length)
            {
                sidecarPath = args[++i];
            }
            else
            {
                Console.Error.WriteLine($"unknown arg: {args[i]}");
                return 1;
            }
        }

        var stdin = Console.In.ReadToEnd();
        string[] boundFiles;
        try
        {
            boundFiles = JsonSerializer.Deserialize<string[]>(stdin) ?? Array.Empty<string>();
        }
        catch (JsonException ex)
        {
            Console.Error.WriteLine("invalid stdin JSON: " + ex.Message);
            return 1;
        }

        // Normalize bound paths to forward slashes so they match SyntaxTree.FilePath.
        var boundRels = new HashSet<string>(StringComparer.Ordinal);
        foreach (var rel in boundFiles) boundRels.Add(rel.Replace('\\', '/'));

        var trees = new List<(string Rel, SyntaxTree Tree, bool IsBound)>(boundFiles.Length);

        foreach (var rel in boundRels)
        {
            var tree = TryParse(rel);
            if (tree is not null) trees.Add((rel, tree, IsBound: true));
        }

        // Compilation roots widen the parse scope. Files already in the bound
        // set are skipped — otherwise the same file would appear twice as
        // separate SyntaxTrees and overload resolution would deduplicate via
        // SymbolEqualityComparer but cost extra parse time.
        if (compilationRoots.Count > 0)
        {
            var cwdAbs = Environment.CurrentDirectory;
            foreach (var root in compilationRoots)
            {
                string rootAbs;
                try { rootAbs = Path.GetFullPath(root); }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"invalid compilation root '{root}': {ex.Message}");
                    continue;
                }
                if (!Directory.Exists(rootAbs))
                {
                    Console.Error.WriteLine($"compilation root missing: {root}");
                    continue;
                }

                foreach (var abs in EnumerateCSharpFiles(rootAbs))
                {
                    string rel;
                    try { rel = Path.GetRelativePath(cwdAbs, abs).Replace('\\', '/'); }
                    catch { continue; }
                    if (boundRels.Contains(rel)) continue;

                    var tree = TryParse(rel);
                    if (tree is not null) trees.Add((rel, tree, IsBound: false));
                }
            }
        }

        // Single compilation across every input file so SemanticModel can
        // resolve cross-file references. No metadata refs needed — we only
        // care about resolving calls between application source symbols.
        var compilation = CSharpCompilation.Create(
            "NebulaKgSymbols",
            syntaxTrees: trees.Select(t => t.Tree),
            references: null,
            options: new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));

        var items = new List<SymbolItem>(capacity: boundRels.Count * 8);
        var sidecar = sidecarPath is not null ? new List<SidecarEntry>() : null;

        foreach (var (rel, tree, isBound) in trees)
        {
            var root = (CompilationUnitSyntax)tree.GetRoot();
            var model = compilation.GetSemanticModel(tree);

            if (isBound)
            {
                foreach (var member in EnumerateTopLevelMembers(root))
                {
                    EmitMember(rel, container: null, member, items, model);
                }
            }
            else if (sidecar is not null)
            {
                CollectSidecar(rel, root, model, boundRels, sidecar);
            }
        }

        Console.Out.Write(JsonSerializer.Serialize(items, JsonOptions));

        if (sidecarPath is not null)
        {
            try
            {
                File.WriteAllText(sidecarPath, JsonSerializer.Serialize(sidecar, JsonOptions));
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"sidecar write failed {sidecarPath}: {ex.Message}");
                return 1;
            }
        }
        return 0;
    }

    private static SyntaxTree? TryParse(string rel)
    {
        string source;
        try { source = File.ReadAllText(rel); }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"read failed {rel}: {ex.Message}");
            return null;
        }
        try
        {
            return CSharpSyntaxTree.ParseText(SourceText.From(source), path: rel);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"parse failed {rel}: {ex.Message}");
            return null;
        }
    }

    private static IEnumerable<string> EnumerateCSharpFiles(string rootAbs)
    {
        // Manual recursion so we can skip bin/obj/node_modules subtrees rather
        // than enumerating them and discarding — generated *.cs under bin/obj
        // can be large and adds nothing to the symbol layer.
        var stack = new Stack<string>();
        stack.Push(rootAbs);
        while (stack.Count > 0)
        {
            var dir = stack.Pop();
            IEnumerable<string> subdirs;
            try { subdirs = Directory.EnumerateDirectories(dir); }
            catch { continue; }
            foreach (var sub in subdirs)
            {
                var name = Path.GetFileName(sub);
                if (name.Equals("bin", StringComparison.OrdinalIgnoreCase)) continue;
                if (name.Equals("obj", StringComparison.OrdinalIgnoreCase)) continue;
                if (name.Equals("node_modules", StringComparison.OrdinalIgnoreCase)) continue;
                stack.Push(sub);
            }
            IEnumerable<string> files;
            try { files = Directory.EnumerateFiles(dir, "*.cs"); }
            catch { continue; }
            foreach (var f in files) yield return f;
        }
    }

    private static void CollectSidecar(
        string sourceRel, CompilationUnitSyntax root, SemanticModel model,
        HashSet<string> boundRels, List<SidecarEntry> sidecar)
    {
        // Dedupe within a source file on (target, line) so a tight loop of
        // identical calls doesn't inflate sidecar volume.
        var seen = new HashSet<(string Name, string? Container, int Line)>();
        foreach (var inv in root.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            var info = model.GetSymbolInfo(inv);
            var symbol = info.Symbol as IMethodSymbol
                ?? info.CandidateSymbols.OfType<IMethodSymbol>().FirstOrDefault();
            if (symbol is null) continue;

            var reduced = symbol.ReducedFrom ?? symbol;

            bool resolvesIntoBound = false;
            foreach (var loc in reduced.Locations)
            {
                if (!loc.IsInSource) continue;
                var declPath = loc.SourceTree?.FilePath;
                if (declPath is null) continue;
                if (boundRels.Contains(declPath))
                {
                    resolvesIntoBound = true;
                    break;
                }
            }
            if (!resolvesIntoBound) continue;

            var name = reduced.Name;
            var container = reduced.ContainingType?.Name;
            var line = inv.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
            if (seen.Add((name, container, line)))
            {
                sidecar.Add(new SidecarEntry(sourceRel, line, new SidecarTarget(name, container)));
            }
        }
    }

    private static IEnumerable<MemberDeclarationSyntax> EnumerateTopLevelMembers(CompilationUnitSyntax root)
    {
        foreach (var m in root.Members)
        {
            if (m is BaseNamespaceDeclarationSyntax ns)
            {
                foreach (var inner in ns.Members) yield return inner;
            }
            else
            {
                yield return m;
            }
        }
    }

    private static void EmitMember(
        string rel, string? container, MemberDeclarationSyntax member,
        List<SymbolItem> items, SemanticModel model)
    {
        switch (member)
        {
            case TypeDeclarationSyntax type:
                EmitType(rel, container, type, items, model);
                break;
            case EnumDeclarationSyntax e:
                items.Add(new SymbolItem(
                    File: rel,
                    Name: e.Identifier.ValueText,
                    Container: container,
                    Kind: "enum",
                    Line: LineOf(e),
                    EndLine: EndLineOf(e),
                    Signature: Signature(e),
                    Visibility: VisibilityOf(e.Modifiers),
                    Calls: Array.Empty<CallRef>(),
                    Implements: Array.Empty<CallRef>(),
                    Instantiates: Array.Empty<CallRef>(),
                    TypeRefs: Array.Empty<CallRef>()));
                break;
            case DelegateDeclarationSyntax d:
                items.Add(new SymbolItem(
                    File: rel,
                    Name: d.Identifier.ValueText,
                    Container: container,
                    Kind: "delegate",
                    Line: LineOf(d),
                    EndLine: EndLineOf(d),
                    Signature: Signature(d),
                    Visibility: VisibilityOf(d.Modifiers),
                    Calls: Array.Empty<CallRef>(),
                    Implements: Array.Empty<CallRef>(),
                    Instantiates: Array.Empty<CallRef>(),
                    TypeRefs: Array.Empty<CallRef>()));
                break;
        }
    }

    private static void EmitType(
        string rel, string? container, TypeDeclarationSyntax type,
        List<SymbolItem> items, SemanticModel model)
    {
        var name = type.Identifier.ValueText;
        var kind = type switch
        {
            InterfaceDeclarationSyntax => "interface",
            RecordDeclarationSyntax => "record",
            StructDeclarationSyntax => "struct",
            _ => "class",
        };

        items.Add(new SymbolItem(
            File: rel,
            Name: name,
            Container: container,
            Kind: kind,
            Line: LineOf(type),
            EndLine: EndLineOf(type),
            Signature: Signature(type),
            Visibility: VisibilityOf(type.Modifiers),
            Calls: Array.Empty<CallRef>(),
            Implements: Array.Empty<CallRef>(),
            Instantiates: Array.Empty<CallRef>(),
            TypeRefs: Array.Empty<CallRef>()));

        foreach (var member in type.Members)
        {
            switch (member)
            {
                case TypeDeclarationSyntax nested:
                    EmitType(rel, name, nested, items, model);
                    break;
                case EnumDeclarationSyntax e:
                    items.Add(new SymbolItem(
                        File: rel,
                        Name: e.Identifier.ValueText,
                        Container: name,
                        Kind: "enum",
                        Line: LineOf(e),
                        EndLine: EndLineOf(e),
                        Signature: Signature(e),
                        Visibility: VisibilityOf(e.Modifiers),
                        Calls: Array.Empty<CallRef>(),
                        Implements: Array.Empty<CallRef>(),
                        Instantiates: Array.Empty<CallRef>(),
                        TypeRefs: Array.Empty<CallRef>()));
                    break;
                case MethodDeclarationSyntax m:
                    items.Add(new SymbolItem(
                        File: rel,
                        Name: m.Identifier.ValueText,
                        Container: name,
                        Kind: "method",
                        Line: LineOf(m),
                        EndLine: EndLineOf(m),
                        Signature: Signature(m),
                        Visibility: VisibilityOf(m.Modifiers),
                        Calls: ResolvedCalls(m, model),
                        Implements: ImplementsOf(m, model),
                        Instantiates: ResolvedInstantiations(m, model),
                        TypeRefs: ResolvedTypeRefsForMethod(m, model)));
                    break;
                case PropertyDeclarationSyntax p:
                    items.Add(new SymbolItem(
                        File: rel,
                        Name: p.Identifier.ValueText,
                        Container: name,
                        Kind: "property",
                        Line: LineOf(p),
                        EndLine: EndLineOf(p),
                        Signature: Signature(p),
                        Visibility: VisibilityOf(p.Modifiers),
                        Calls: ResolvedCalls(p, model),
                        Implements: Array.Empty<CallRef>(),
                        Instantiates: ResolvedInstantiations(p, model),
                        TypeRefs: ResolvedTypeRefsForProperty(p, model)));
                    break;
                case ConstructorDeclarationSyntax ctor:
                    // Emit constructor with synthetic name ".ctor" so its symbol
                    // id is distinct from the type's symbol id.
                    items.Add(new SymbolItem(
                        File: rel,
                        Name: ".ctor",
                        Container: name,
                        Kind: "constructor",
                        Line: LineOf(ctor),
                        EndLine: EndLineOf(ctor),
                        Signature: Signature(ctor),
                        Visibility: VisibilityOf(ctor.Modifiers),
                        Calls: ResolvedCalls(ctor, model),
                        Implements: Array.Empty<CallRef>(),
                        Instantiates: ResolvedInstantiations(ctor, model),
                        TypeRefs: ResolvedTypeRefsForConstructor(ctor, model)));
                    break;
            }
        }
    }

    private static int LineOf(SyntaxNode node) =>
        node.GetLocation().GetLineSpan().StartLinePosition.Line + 1;

    private static int EndLineOf(SyntaxNode node) =>
        node.GetLocation().GetLineSpan().EndLinePosition.Line + 1;

    private static string VisibilityOf(SyntaxTokenList modifiers)
    {
        var hasPublic = false;
        var hasInternal = false;
        var hasProtected = false;
        var hasPrivate = false;
        foreach (var m in modifiers)
        {
            if (m.IsKind(SyntaxKind.PublicKeyword)) hasPublic = true;
            else if (m.IsKind(SyntaxKind.InternalKeyword)) hasInternal = true;
            else if (m.IsKind(SyntaxKind.ProtectedKeyword)) hasProtected = true;
            else if (m.IsKind(SyntaxKind.PrivateKeyword)) hasPrivate = true;
        }
        if (hasPublic) return "public";
        if (hasInternal) return "internal";
        if (hasProtected) return "protected";
        if (hasPrivate) return "private";
        return "internal";
    }

    private static string Signature(MemberDeclarationSyntax node)
    {
        int start = int.MaxValue;
        if (node.Modifiers.Count > 0)
        {
            start = Math.Min(start, node.Modifiers[0].SpanStart);
        }
        foreach (var child in node.ChildNodes())
        {
            if (child is AttributeListSyntax) continue;
            start = Math.Min(start, child.SpanStart);
        }
        if (start == int.MaxValue || start < node.SpanStart) start = node.SpanStart;
        var end = node.Span.End;
        var text = node.SyntaxTree.GetText().ToString(new Microsoft.CodeAnalysis.Text.TextSpan(start, end - start));
        var cut = text.Length;
        var braceIdx = text.IndexOf('{');
        if (braceIdx > 0) cut = Math.Min(cut, braceIdx);
        var arrowIdx = text.IndexOf("=>", StringComparison.Ordinal);
        if (arrowIdx > 0) cut = Math.Min(cut, arrowIdx);
        var semiIdx = text.IndexOf(';');
        if (semiIdx > 0) cut = Math.Min(cut, semiIdx);
        var nlIdx = text.IndexOf('\n');
        if (nlIdx > 0) cut = Math.Min(cut, nlIdx);
        return text.Substring(0, cut).Trim();
    }

    private static CallRef[] ResolvedCalls(SyntaxNode body, SemanticModel model)
    {
        // De-duplicate on (name, container) so we don't emit the same edge twice
        // when the same method is invoked from multiple call sites in the body.
        var seen = new HashSet<(string Name, string? Container)>();
        var result = new List<CallRef>();

        foreach (var inv in body.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            var info = model.GetSymbolInfo(inv);
            var symbol = info.Symbol as IMethodSymbol
                ?? info.CandidateSymbols.OfType<IMethodSymbol>().FirstOrDefault();

            string name;
            string? container;
            if (symbol is not null)
            {
                // Reduced symbol drops extension-method receiver substitution so
                // we report the actual method name a reader would grep for.
                var reduced = symbol.ReducedFrom ?? symbol;
                name = reduced.Name;
                container = reduced.ContainingType?.Name;
            }
            else
            {
                name = ExtractCallName(inv) ?? "";
                container = null;
                if (string.IsNullOrEmpty(name)) continue;
            }

            if (seen.Add((name, container)))
            {
                result.Add(new CallRef(name, container));
            }
        }

        return result.ToArray();
    }

    private static string? ExtractCallName(InvocationExpressionSyntax inv) => inv.Expression switch
    {
        IdentifierNameSyntax id => id.Identifier.ValueText,
        MemberAccessExpressionSyntax ma => ma.Name.Identifier.ValueText,
        GenericNameSyntax gn => gn.Identifier.ValueText,
        MemberBindingExpressionSyntax mb => mb.Name.Identifier.ValueText,
        _ => null,
    };

    private static CallRef[] ImplementsOf(MethodDeclarationSyntax method, SemanticModel model)
    {
        if (model.GetDeclaredSymbol(method) is not IMethodSymbol symbol)
            return Array.Empty<CallRef>();

        var refs = new List<CallRef>();

        // Explicit interface implementations (e.g., void IFoo.Bar() { ... }).
        foreach (var explicitImpl in symbol.ExplicitInterfaceImplementations)
        {
            if (explicitImpl.ContainingType is { } t)
                refs.Add(new CallRef(explicitImpl.Name, t.Name));
        }

        // Implicit interface implementations. For each interface the containing
        // type implements, check whether this method is the implementing member.
        var containingType = symbol.ContainingType;
        if (containingType is not null)
        {
            foreach (var iface in containingType.AllInterfaces)
            {
                foreach (var ifaceMember in iface.GetMembers().OfType<IMethodSymbol>())
                {
                    if (ifaceMember.Name != symbol.Name) continue;
                    var impl = containingType.FindImplementationForInterfaceMember(ifaceMember);
                    if (SymbolEqualityComparer.Default.Equals(impl, symbol))
                    {
                        refs.Add(new CallRef(ifaceMember.Name, iface.Name));
                    }
                }
            }
        }

        // Overridden virtual/abstract base method — same dispatch concern.
        if (symbol.OverriddenMethod is { ContainingType: { } baseType } overridden)
        {
            refs.Add(new CallRef(overridden.Name, baseType.Name));
        }

        return refs
            .GroupBy(r => (r.Name, r.Container))
            .Select(g => g.First())
            .ToArray();
    }

    private static CallRef[] ResolvedInstantiations(SyntaxNode body, SemanticModel model)
    {
        // Walk every `new T(...)` (explicit and target-typed) inside the body
        // and emit one edge per distinct target type. Resolved via SemanticModel
        // so cross-namespace types are correct.
        var seen = new HashSet<(string Name, string? Container)>();
        var result = new List<CallRef>();

        foreach (var node in body.DescendantNodes())
        {
            INamedTypeSymbol? type = node switch
            {
                ObjectCreationExpressionSyntax oc => model.GetSymbolInfo(oc).Symbol is IMethodSymbol m
                    ? m.ContainingType
                    : model.GetTypeInfo(oc).Type as INamedTypeSymbol,
                ImplicitObjectCreationExpressionSyntax ioc => model.GetSymbolInfo(ioc).Symbol is IMethodSymbol im
                    ? im.ContainingType
                    : model.GetTypeInfo(ioc).Type as INamedTypeSymbol,
                _ => null,
            };
            if (type is null) continue;
            var key = (type.Name, type.ContainingType?.Name);
            if (seen.Add(key))
            {
                result.Add(new CallRef(type.Name, type.ContainingType?.Name));
            }
        }
        return result.ToArray();
    }

    private static CallRef[] ResolvedTypeRefsForMethod(MethodDeclarationSyntax method, SemanticModel model)
    {
        if (model.GetDeclaredSymbol(method) is not IMethodSymbol symbol)
            return Array.Empty<CallRef>();

        var seen = new HashSet<(string Name, string? Container)>();
        var result = new List<CallRef>();
        AddTypeRef(symbol.ReturnType, seen, result);
        foreach (var param in symbol.Parameters)
            AddTypeRef(param.Type, seen, result);
        foreach (var typeParam in symbol.TypeParameters)
            foreach (var constraint in typeParam.ConstraintTypes)
                AddTypeRef(constraint, seen, result);
        return result.ToArray();
    }

    private static CallRef[] ResolvedTypeRefsForProperty(PropertyDeclarationSyntax property, SemanticModel model)
    {
        if (model.GetDeclaredSymbol(property) is not IPropertySymbol symbol)
            return Array.Empty<CallRef>();

        var seen = new HashSet<(string Name, string? Container)>();
        var result = new List<CallRef>();
        AddTypeRef(symbol.Type, seen, result);
        return result.ToArray();
    }

    private static CallRef[] ResolvedTypeRefsForConstructor(ConstructorDeclarationSyntax ctor, SemanticModel model)
    {
        if (model.GetDeclaredSymbol(ctor) is not IMethodSymbol symbol)
            return Array.Empty<CallRef>();

        var seen = new HashSet<(string Name, string? Container)>();
        var result = new List<CallRef>();
        foreach (var param in symbol.Parameters)
            AddTypeRef(param.Type, seen, result);
        return result.ToArray();
    }

    // Add a type plus its generic type arguments, recursively. Built-in primitives
    // and System.* anchors are skipped — they're noise that never resolves to a
    // bound symbol anyway. The orchestrator further drops self-edges.
    private static void AddTypeRef(
        ITypeSymbol? type,
        HashSet<(string Name, string? Container)> seen,
        List<CallRef> result)
    {
        if (type is null) return;
        if (type is INamedTypeSymbol named)
        {
            var name = named.Name;
            if (!string.IsNullOrEmpty(name) && !IsBuiltInOrSystemAnchor(named))
            {
                var key = (name, named.ContainingType?.Name);
                if (seen.Add(key))
                    result.Add(new CallRef(name, named.ContainingType?.Name));
            }
            foreach (var arg in named.TypeArguments)
                AddTypeRef(arg, seen, result);
        }
        else if (type is IArrayTypeSymbol array)
        {
            AddTypeRef(array.ElementType, seen, result);
        }
    }

    private static bool IsBuiltInOrSystemAnchor(INamedTypeSymbol type)
    {
        if (type.SpecialType != SpecialType.None) return true; // int, string, bool, object, etc.
        var ns = type.ContainingNamespace?.ToDisplayString() ?? "";
        // Common framework anchors that would otherwise dominate type_refs.
        return ns == "System" || ns.StartsWith("System.", StringComparison.Ordinal);
    }
}
