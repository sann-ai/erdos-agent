# Mathematical Knowledge Base

The knowledge base follows Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern: immutable raw sources, an LLM-maintained wiki, and a schema that tells agents how to maintain it. For mathematics, this project adds first-class storage for examples.

## Layout

```text
kb/
  raw/
    papers/
  wiki/
    problems/
    papers/
    methods/
  examples/
  method_cards/
  index.md
  log.md
  schema.md
```

## Why Examples Are First-Class

For mathematical research, examples are not just illustrations. They are often:

- extremizers
- counterexamples
- small cases
- model constructions
- witnesses for sharp constants
- sanity checks for a Lean statement
- seeds for computation

Agents should store examples even when they do not immediately solve a problem.

## Method Cards

A method card should describe a reusable proof or computation pattern:

```markdown
# Method Card: short name

## Source

## Core Idea

## Applies When

## Fails When

## Examples

## Related Problems

## Formalization Notes
```

Method Cards are the bridge from "a problem was solved" to "try the same move on nearby open problems".
