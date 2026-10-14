# Soumya's Real-Time Stats API (LeetCode + GitHub)

A high-performance, serverless animated SVG stats engine deployed on Vercel.

## Endpoints

### LeetCode
- `GET /card.svg` - Main LeetCode progress donut card with Easy/Medium/Hard bars, streak, badge, and global rank.
- `GET /badges.svg` - Earned LeetCode badges with retina embedded icons and issue dates.
- `GET /streak.svg` - 3-column stats card with animated green streak ring.

### GitHub (Real-Time)
- `GET /github-heatmap.svg` - Full 53-week contribution calendar heatmap with stagger animation.
- `GET /github-streak.svg` - 3-column contributions streak card with animated green ring.

## Features
- **Real-Time Data**: Queries LeetCode GraphQL & GitHub public contributions dynamically on demand.
- **Vercel Edge Caching**: 2-minute memory/edge cache with `stale-while-revalidate` ensures fast response times (~20ms) and prevents rate-limiting.
- **Zero Client Dependencies**: Pure vector animated SVGs compatible with GitHub READMEs.
