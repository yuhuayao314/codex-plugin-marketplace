# Windows Computer Use architecture

Treat Computer Use on Windows as three independent layers. A visible settings switch proves only that one UI path rendered; it does not prove that the complete control path is live.

## Layer 1: signed package and availability gates

Codex Desktop is distributed as a signed MSIX. UI routes and Windows Computer Use availability checks live in the packaged application bundle. Store updates replace that signed package, including any local package-level gate changes.

This is why Computer Use can remain available on macOS while Windows needs additional recovery work. The platforms use different bundles, helper processes, signing and rollout paths. It is not evidence that the Windows download was incomplete.

## Layer 2: writable Computer Use runtimes

Computer Use depends on helper executables that may need to be relocated to a writable runtime directory. WindowsApps files can be enumerable and hashable while normal copying is denied because of package encryption or access rules.

The characteristic failure is bundled_executable_relocation_failed. Repair requires an unencrypted source from the exact same Codex build and an expected SHA256. A file from a newer or older build is not an acceptable substitute.

## Layer 3: live process, tool schema and named pipe

Repairing files does not mutate the schema already loaded by a running desktop process. A task opened inside that process may continue to lack Computer Use or its helper transport.

Computer Use uses process-specific named pipes. SKY_CUA_NATIVE_PIPE and SKY_CUA_NATIVE_PIPE_DIRECTORY must not be persisted in configuration because their values change across process lifetimes.

The correct transition is a package-scoped restart followed by a genuinely fresh task.

## End-to-end flow

    Signed Computer Use gates
              |
              v
    Writable helper runtimes
              |
              v
    Live tool schema and named pipe
              |
              v
    Visible application interaction

Each arrow is an explicit verification boundary. Do not skip directly from a visible setting to a claim of success.
