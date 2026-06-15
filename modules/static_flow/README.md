# Static Flow Core

This package is the project-level static flow core.

The intended architecture is:

```text
language source -> language adapter -> StaticProjectGraph -> analysis / visualization
```

V1 ships a Python adapter backed by the standard library `ast` module because it
is deterministic and already validates the first product loop. Additional
languages should be added as adapters that emit the same `contracts.static_flow`
types. Tree-sitter is the preferred backend for those adapters because it gives
one parsing framework for Java, JavaScript/TypeScript, Go, Rust, and other
languages.

Core layers must not depend on Python AST or Tree-sitter CST. That dependency
belongs inside each adapter.
