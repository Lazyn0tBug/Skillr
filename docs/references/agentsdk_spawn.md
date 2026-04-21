How Slash Commands Spawn Sub-Agents in Claude Code
The Core Concept
Slash commands can orchestrate other behavior — you can spell out in the command itself that it should spin up a subagent (or a specific subagent), call out a particular skill/workflow, and generally "pipeline" the work (e.g., research → codebase scan → write a doc) instead of doing everything in one shot.

Part 1: Defining a Slash Command
Custom slash commands are stored in designated directories based on their scope:

Project commands: .claude/commands/ — available only in the current project
Personal commands: ~/.claude/commands/ — available across all your projects
Each command is a markdown file with frontmatter. Example .claude/commands/research.md:

---
description: Research a problem using web search and codebase exploration
allowed-tools: Task, WebSearch, WebFetch, Grep, Glob, Read, Write
---

# Research: $ARGUMENTS

Research the following: > **$ARGUMENTS**

Use the Task tool to spawn these subagents **in parallel**:
1. **Web Agent** (subagent_type: general-purpose) — search docs and best practices
2. **Codebase Agent** (subagent_type: general-purpose) — grep and explore local code
Custom commands support dynamic arguments using $1, $2 placeholders (or $ARGUMENTS for the whole input).

Part 2: Defining Sub-Agents (File-Based)
Agents are defined in markdown with specific front matter. They live in either a global context (~/.claude/agents) or in a project context (project/.claude/agents), and where they are defined determines where you can use them.

Example .claude/agents/code-reviewer.md:

---
description: Reviews code for bugs, security issues, and style
allowed-tools: Read, Grep, Glob
model: claude-haiku-4-5
---

You are a code reviewer. Analyze the provided files for:
- Security vulnerabilities
- Logic errors
- Code style issues

Return a concise, actionable report.
Each subagent runs in its own context window with a custom system prompt, specific tool access, and independent permissions. When Claude encounters a task that matches a subagent's description, it delegates to that subagent, which works independently and returns results.

Part 3: Programmatic Sub-Agents (Agent SDK)
If you're using the @anthropic-ai/claude-agent-sdk, you can define sub-agents in code:

Define subagents directly in your code using the agents parameter. The Agent tool must be included in allowedTools since Claude invokes subagents through the Agent tool.

import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "/research my-topic",
  options: {
    maxTurns: 10,
    allowedTools: ["Agent", "Read", "Grep"],
    agents: [
      {
        name: "web-researcher",
        description: "Searches the web for documentation and examples",
        systemPrompt: "You are a web research specialist...",
        allowedTools: ["WebSearch", "WebFetch"],
      },
      {
        name: "code-analyzer",
        description: "Analyzes local code structure",
        systemPrompt: "You are a code analysis specialist...",
        allowedTools: ["Read", "Grep", "Glob"],
        model: "claude-haiku-4-5-20251001", // cheaper model
      }
    ]
  }
})) {
  if (message.type === "assistant") {
    console.log(message.message);
  }
}
A subagent's context window starts fresh (no parent conversation) but isn't empty. The only channel from parent to subagent is the Agent tool's prompt string, so include any file paths, error messages, or decisions the subagent needs directly in that prompt.

Key Benefits of Subagents
Subagents help you:

Preserve context by keeping exploration and implementation out of your main conversation
Enforce constraints by limiting which tools a subagent can use
Control costs by routing tasks to faster, cheaper models like Haiku
Specialize behavior with focused system prompts for specific domains
Recommended References


Resource	URL
Official Sub-Agents Docs	https://code.claude.com/docs/en/sub-agents
Agent SDK – Slash Commands	https://docs.claude.com/en/docs/agent-sdk/slash-commands
Agent SDK – Subagents	https://platform.claude.com/docs/en/agent-sdk/subagents
Awesome Claude Code (community)	https://github.com/hesreallyhim/awesome-claude-code
Claude Code System Prompts (reverse-engineered)	https://github.com/Piebald-AI/claude-code-system-prompts
The key pattern is: your slash command markdown instructs Claude to use the Task tool (or Agent tool), which is what actually spawns the sub-agent. Make sure Task or Agent is listed in your command's allowed-tools frontmatter.
