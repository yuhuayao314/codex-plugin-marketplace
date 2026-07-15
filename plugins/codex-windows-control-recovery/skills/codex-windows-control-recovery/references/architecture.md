# Windows control architecture

Treat the Windows control stack as four independent layers. A visible settings switch proves only that one UI path rendered; it does not prove that the complete control path is live.

## Layer 1: signed package and availability gates

Codex Desktop is distributed as a signed MSIX. UI routes and availability checks live in the packaged application bundle. Store updates replace that signed package, including any local package-level gate changes.

This is why a feature can remain available on macOS while Windows needs additional recovery work. The platforms use different bundles, helper processes, signing and rollout paths. It is not evidence that the Windows download was incomplete.

## Layer 2: writable runtimes

Some bundled executables must be relocated to a writable runtime directory before use. WindowsApps files can be enumerable and hashable while normal copying is denied because of package encryption or access rules.

The characteristic failure is bundled_executable_relocation_failed. Repair requires an unencrypted source from the exact same Codex build and an expected SHA256. A file from a newer or older build is not an acceptable substitute.

## Layer 3: live process, tool schema and named pipes

Repairing files does not mutate the schema already loaded by a running desktop process. A conversation opened inside that process may continue to lack Computer Use or node_repl.

Computer Use also uses process-specific named pipes. SKY_CUA_NATIVE_PIPE and SKY_CUA_NATIVE_PIPE_DIRECTORY must not be persisted in configuration because their values change across process lifetimes.

The correct transition is a package-scoped restart followed by a genuinely fresh task.

## Layer 4: browser destination policy and extension state

The in-app browser, external Chrome control, and Windows Computer Use are separate systems.

An enterprise destination policy can block example.com, file URLs, localhost, or another target while the browser backend is healthy. External Chrome can separately report that its extension is not connected. Neither condition proves that Computer Use installation failed.

Do not bypass policy or change the proxy during recovery. Report the exact boundary and test an allowed destination.

## End-to-end flow

    Signed package gates
            |
            v
    Writable helper runtimes
            |
            v
    Live desktop tool schema and named pipe
            |
            v
    Browser policy or target application

Each arrow is an explicit verification boundary. Do not skip directly from a visible setting to a claim of success.
