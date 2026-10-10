# Soumya's Real-Time LeetCode Stats API

A high-performance, serverless animated SVG stats engine deployed on Vercel.

## Endpoints

- `GET /card.svg` - Main LeetCode progress donut card with Easy/Medium/Hard bars, streak, badge, and global rank.
- `GET /badges.svg` - Earned LeetCode badges with retina embedded icons and issue dates.
- `GET /streak.svg` - 3-column stats card with animated green streak ring.

## Features
- **Real-Time Data**: Queries LeetCode's public GraphQL API on demand.
- **Vercel Edge Caching**: 2-minute memory/edge cache with `stale-while-revalidate` ensures fast response times (~20ms) and prevents rate-limiting.
- **Zero Client Dependencies**: Pure vector animated SVGs compatible with GitHub READMEs.
