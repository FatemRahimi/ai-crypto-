# UI and UX

The interface is a desktop-first working surface for one operator. It should feel like a calm research notebook, not a trading pit.

## Tone

- Warm paper background, ink text, one deep green used for navigation and answers.
- Serif titles, a compact sans for everything else. The fonts are the Windows system stack so a build does not depend on a font download.
- Sample material uses a dashed border and a Demo mark.
- Numbers that the system cannot verify are omitted. An em dash means "not available", not zero.

## Navigation

Home, Strategy, Opportunities, Positions, Research, Performance, Account.

The current page is marked with `aria-current`. A skip link goes to the main content.

## Home

The command center answers five questions from the real Phase 1 state:

1. What is BTC doing? No verified market data.
2. Is there an opportunity? Not evaluated.
3. What does AI recommend? Not evaluated.
4. What is my current risk? No account risk on file.
5. Do I need to do anything? Nothing in this build.

Below that, a demonstration layout shows the future panels: BTC status, AI view, strategy, position, account risk, weekly objective, opportunity, and notification. The AI view lists LONG, SHORT, WAIT, and NO TRADE, and marks WAIT as a sample state.

The chart is an empty frame. The copilot composer is disabled. A local API line reports whether the backend process is reachable. That line is not a market status.

## Other sections

- Strategy: a form for future intent. Submit keeps the text on the page and does not call the network. Approve is disabled. Quant status reads "Not run".
- Opportunities: the four states, then a sample card whose fields are empty. No probabilities.
- Positions: field list and disabled actions (hold, reduce, partial exit, exit, protect).
- Research: technical, profile, order flow, derivatives, fundamental, and quant groups. They are closed until opened, and each says that no evidence is connected.
- Performance: empty sections. No sample curve.
- Account: capital, connections, security, notifications, permissions, sessions, and audit. Planned items are tagged Planned. There is no credential input.

## Progressive disclosure

Research groups use closed disclosure elements. Advanced vocabulary is visible as a list of future topics, not as a wall of indicators.

## Error handling

The application error view tells the operator the page failed and offers a retry. It does not print the exception. Unknown addresses have a plain not-found page.

## What the interface must not become

- A flashing execution ticket
- A generic administration grid of every database table
- A place where demo copy can be confused with a book of record

If a later phase adds a live figure, the Demo mark comes off only for that figure, and the figure's source is visible.
