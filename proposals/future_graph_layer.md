# Future Graph Layer

A graph layer should model explicit relationships, not become a second memory platform.

Good graph edges:

- project -> decision -> bug -> fix
- skill -> reference -> script
- report -> canonical rule -> follow-up

Bad graph edges:

- every conversation turn
- every tool output
- inferred personal facts without a canonical source

The graph should remain rebuildable from trusted files and should never override canonical state.
