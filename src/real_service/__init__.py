"""F1 R5: the executor-side service layer of the real gateway: the world builders and the create, read, reproduce and list service.

This package sits above `persistence` (it calls the performance engine and its service, which `persistence` must not import). It imports from
`web_api` exactly one module, the pure scoped-contract leaf (no route, no store, no connection), which supplies the create-intent validator, the
label field names and the list-entry shape; it imports no route, app or launcher (a static test checks the leaf's import closure and that nothing
else imports it). R7 installs the contract in the real-mode app; nothing here is a route. (An earlier docstring said this package was "below
`web_api`"; that was not the real layering. TR5 observation.)
"""
