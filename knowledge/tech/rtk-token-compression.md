---
title: "RTK (Rust Token Killer) CLI Tool"
domain: "tech"
last_updated: "2026-04-15"
confidence: "medium"
sources: ["file: C:\temp\test-source-rtk.txt"]
---

## Summary
RTK (Rust Token Killer) is an open-source [[Rust]] [[CLI Tool]] designed to function as a proxy between [[Claude Code]] and terminal commands. Its primary function is to compress command output by 60-90% before it enters the context window, thereby saving tokens and reducing operational costs.

## Content

### Overview and Functionality
*   **Definition:** RTK is an open-source [[Rust]] [[CLI Tool]] developed by rtk-ai.
*   **Purpose:** It acts as a proxy layer between [[Claude Code]] and standard terminal commands.
*   **Core Mechanism:** It compresses command output by an estimated 60-90%.
*   **Benefits:** This compression saves tokens and reduces cost when using [[Claude Code]].
*   **Filters:** RTK includes dedicated filters for common command-line utilities, including `git`, `cargo`, `npm`, `docker`, and `kubectl`. If a specific filter is not available, the command output is passed through unchanged.

### Installation and Usage Details
*   **Version:** The installed version is v0.36.0.
*   **Windows Implementation:** On Windows, RTK utilizes `CLAUDE.md` injection mode because hook-based mode requires a Unix environment.
*   **Configuration:** When installed on Windows, it creates a global `CLAUDE.md` file at `C:\Users\jerme\.claude\CLAUDE.md`.
*   **Instructions:** This configuration file provides instructions for [[Claude Code]] to prefix all commands with "rtk".
*   **Deployment Record:** RTK was installed on Jermey's machine on 2026-04-15.
*   **Privacy:** Telemetry was declined during setup.

### Maintenance and Resources
*   **Maintainer:** RTK AI Labs.
*   **Contact:** contact@rtk-ai.app.
*   **Repository:** The GitHub repository is located at https://github.com/rtk-ai/rtk.

## Changelog
- 2026-04-15: Created -- source: file: C:\temp\test-source-rtk.txt
