# Clean Architecture Guide

## Rules
- Domain has no dependencies
- Application depends on Domain only
- Infrastructure implements Application interfaces
- API depends on Application only

## Anti-Patterns
- API directly querying DbContext
- Domain referencing EF Core types
