# First outside contribution: what made it work

AgentCron's first outside code contribution was a dependency-free webhook notification adapter.

## Timeline

- The repository published a focused issue describing one unattended-agent failure mode: final failures were only visible in local logs.
- The issue offered two bounded implementation choices and asked contributors to coordinate before opening a pull request.
- An outside contributor forked the repository and opened pull request #3 with implementation, tests, documentation, and explicit privacy decisions.
- The change passed isolated CI, was reviewed, merged, credited, and then hardened before the v0.3.0 release.

## Why the task was approachable

The issue specified behavior rather than dictating every line of implementation:

- notifications are opt-in;
- prompt text and output stay private unless explicitly enabled;
- notification errors never replace the real job result;
- tests mock network access;
- the core remains dependency-free;
- the README includes a configuration example.

That combination kept the task small while preserving product and security boundaries.

## Pattern for future contribution tasks

A useful first issue should contain:

1. one user-visible failure mode;
2. a small, reviewable change surface;
3. exact acceptance criteria;
4. a test strategy that works offline;
5. explicit privacy and compatibility boundaries;
6. a clear statement of what is out of scope.

The project will continue to use this format for community tasks. See the open `good first issue` queue or start a Discussion with a real unattended-agent failure you want to make reproducible.
