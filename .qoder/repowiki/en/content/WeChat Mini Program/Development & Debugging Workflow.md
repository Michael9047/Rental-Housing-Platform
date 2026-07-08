# Development & Debugging Workflow

<cite>
**Referenced Files in This Document**
- [app.js](file://wechat-miniprogram/app.js)
- [app.json](file://wechat-miniprogram/app.json)
- [project.config.json](file://wechat-miniprogram/project.config.json)
- [app.config.js](file://wechat-miniprogram/app.config.js)
- [utils/api.js](file://wechat-miniprogram/utils/api.js)
- [utils/auth.js](file://wechat-miniprogram/utils/auth.js)
- [pages/index/index.js](file://wechat-miniprogram/pages/index/index.js)
- [components/property-card/property-card.js](file://wechat-miniprogram/components/property-card/property-card.js)
- [components/search-bar/search-bar.js](file://wechat-miniprogram/components/search-bar/search-bar.js)
- [components/map-view/map-view.js](file://wechat-miniprogram/components/map-view/map-view.js)
- [sitemap.json](file://wechat-miniprogram/sitemap.json)
- [README.md](file://README.md)
- [DEPLOYMENT.md](file://DEPLOYMENT.md)
</cite>

## Table of Contents
1. Introduction
2. Project Structure
3. Core Components
4. Architecture Overview
5. Detailed Component Analysis
6. Dependency Analysis
7. Performance Considerations
8. Troubleshooting Guide
9. Conclusion
10. Appendices

## Introduction
This document provides a comprehensive development and debugging workflow for the WeChat Mini Program within this project. It covers environment setup, WeChat DevTools usage (console, network inspection, performance profiling), JavaScript error debugging, network request troubleshooting, component debugging, testing strategies, code organization best practices, version control workflows, collaboration tips, common pitfalls, and performance optimization techniques. The guidance is tailored to the actual implementation present in the repository’s wechat-miniprogram directory.

## Project Structure
The WeChat Mini Program follows the standard structure with pages, components, utilities, and configuration files:
- Pages: index, search, property, chat, booking, me
- Components: property-card, search-bar, map-view
- Utilities: api.js (HTTP wrapper), auth.js (WeChat login flow)
- Configuration: app.json (routing, tabBar, permissions), project.config.json (DevTools settings), app.config.js (environment-specific API base URLs), sitemap.json

```mermaid
graph TB
subgraph "Mini Program"
A["app.js"]
B["app.json"]
C["project.config.json"]
D["app.config.js"]
E["sitemap.json"]
U1["utils/api.js"]
U2["utils/auth.js"]
P1["pages/index/index.js"]
C1["components/property-card/property-card.js"]
C2["components/search-bar/search-bar.js"]
C3["components/map-view/map-view.js"]
end
A --> U1
A --> U2
P1 --> U1
P1 --> U2
C1 --> A
C2 --> A
C3 --> A
B --> P1
C --> A
D --> U1
E --> B
```

**Diagram sources**
- [app.js:1-21](file://wechat-miniprogram/app.js#L1-L21)
- [app.json:1-57](file://wechat-miniprogram/app.json#L1-L57)
- [project.config.json:1-37](file://wechat-miniprogram/project.config.json#L1-L37)
- [app.config.js:1-16](file://wechat-miniprogram/app.config.js#L1-L16)
- [sitemap.json:1-7](file://wechat-miniprogram/sitemap.json#L1-L7)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [utils/auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [pages/index/index.js:1-74](file://wechat-miniprogram/pages/index/index.js#L1-L74)
- [components/property-card/property-card.js:1-30](file://wechat-miniprogram/components/property-card/property-card.js#L1-L30)
- [components/search-bar/search-bar.js:1-17](file://wechat-miniprogram/components/search-bar/search-bar.js#L1-L17)
- [components/map-view/map-view.js:1-29](file://wechat-miniprogram/components/map-view/map-view.js#L1-L29)

**Section sources**
- [app.js:1-21](file://wechat-miniprogram/app.js#L1-L21)
- [app.json:1-57](file://wechat-miniprogram/app.json#L1-L57)
- [project.config.json:1-37](file://wechat-miniprogram/project.config.json#L1-L37)
- [app.config.js:1-16](file://wechat-miniprogram/app.config.js#L1-L16)
- [sitemap.json:1-7](file://wechat-miniprogram/sitemap.json#L1-L7)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [utils/auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [pages/index/index.js:1-74](file://wechat-miniprogram/pages/index/index.js#L1-L74)
- [components/property-card/property-card.js:1-30](file://wechat-miniprogram/components/property-card/property-card.js#L1-L30)
- [components/search-bar/search-bar.js:1-17](file://wechat-miniprogram/components/search-bar/search-bar.js#L1-L17)
- [components/map-view/map-view.js:1-29](file://wechat-miniprogram/components/map-view/map-view.js#L1-L29)

## Core Components
- Application bootstrap and global state:
  - App initialization checks login status on launch and maintains global flags and user info.
- Environment configuration:
  - Centralized environment config defines baseUrl and wsUrl for development and production.
- HTTP client wrapper:
  - Unified request function adds Authorization headers, handles token expiration, and shows toast notifications.
- Authentication utility:
  - Implements WeChat login flow, stores tokens locally, and exposes helpers to check login state and logout.
- Page entry:
  - Index page loads recommended properties after authentication and supports navigation and pull-to-refresh.
- Reusable components:
  - Property card computes image URL using global baseUrl; search bar emits input/search events; map view renders default markers based on coordinates.

Key responsibilities and interactions are illustrated below.

**Section sources**
- [app.js:1-21](file://wechat-miniprogram/app.js#L1-L21)
- [app.config.js:1-16](file://wechat-miniprogram/app.config.js#L1-L16)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [utils/auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [pages/index/index.js:1-74](file://wechat-miniprogram/pages/index/index.js#L1-L74)
- [components/property-card/property-card.js:1-30](file://wechat-miniprogram/components/property-card/property-card.js#L1-L30)
- [components/search-bar/search-bar.js:1-17](file://wechat-miniprogram/components/search-bar/search-bar.js#L1-L17)
- [components/map-view/map-view.js:1-29](file://wechat-miniprogram/components/map-view/map-view.js#L1-L29)

## Architecture Overview
The mini program architecture centers around a small set of modules:
- App lifecycle initializes global state and triggers login checks.
- Auth module orchestrates WeChat login and persists tokens.
- API module wraps wx.request, injects Authorization, and normalizes errors.
- Pages consume services and update UI via setData.
- Components encapsulate UI logic and emit events to parent pages.

```mermaid
sequenceDiagram
participant MP as "Mini Program"
participant App as "App (app.js)"
participant Auth as "Auth (utils/auth.js)"
participant API as "API (utils/api.js)"
participant Backend as "Backend API"
MP->>App : Launch
App->>Auth : checkLogin()
alt Token exists
Auth-->>App : resolved (isLoggedIn=true)
else No token
Auth->>MP : wx.login()
MP-->>Auth : {code}
Auth->>API : POST /wechat/auth/wechat/login
API->>Backend : HTTP request
Backend-->>API : {access_token, user}
API-->>Auth : data
Auth->>MP : setStorageSync(access_token,user)
Auth-->>App : resolved
end
```

**Diagram sources**
- [app.js:1-21](file://wechat-miniprogram/app.js#L1-L21)
- [utils/auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)

## Detailed Component Analysis

### Authentication Flow
The authentication flow ensures users are logged in before accessing protected features. It uses WeChat’s login code exchange with the backend to obtain a JWT access token and stores it locally.

```mermaid
flowchart TD
Start(["Start"]) --> CheckToken["Check local storage for access_token"]
CheckToken --> HasToken{"Token found?"}
HasToken --> |Yes| SetGlobal["Set global isLoggedIn and userInfo"]
SetGlobal --> End(["Done"])
HasToken --> |No| WxLogin["Call wx.login()"]
WxLogin --> GotCode{"Got code?"}
GotCode --> |No| Reject["Reject with error"]
GotCode --> |Yes| Exchange["POST /wechat/auth/wechat/login with code"]
Exchange --> Success{"Success?"}
Success --> |No| Reject
Success --> Store["Store access_token and user in storage"]
Store --> SetGlobal
Reject --> End
```

**Diagram sources**
- [utils/auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)

**Section sources**
- [utils/auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)

### HTTP Client Wrapper
The API wrapper centralizes request handling, header injection, and error management. It also handles token expiration by clearing local storage and notifying the user.

```mermaid
flowchart TD
Entry(["request(options)"]) --> BuildHeader["Build header with Content-Type<br/>and optional Authorization"]
BuildHeader --> CallWx["wx.request({ url, method, data, header })"]
CallWx --> OnSuccess{"statusCode 2xx?"}
OnSuccess --> |Yes| Resolve["Resolve with response.data"]
OnSuccess --> |No| HandleError["Handle 401 or other errors<br/>show toast and reject"]
CallWx --> OnFail["Network fail"]
OnFail --> ShowToast["Show 'network request failed' toast"]
ShowToast --> Reject["Reject with error"]
HandleError --> End(["End"])
Resolve --> End
Reject --> End
```

**Diagram sources**
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)

**Section sources**
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)

### Index Page Data Loading
The index page performs authentication before loading recommended properties and supports pull-to-refresh and navigation.

```mermaid
sequenceDiagram
participant Page as "Index Page"
participant Auth as "Auth"
participant API as "API"
participant Backend as "Backend API"
Page->>Auth : checkLogin()
Auth-->>Page : resolved
Page->>API : GET /properties?page=1&size=10
API->>Backend : HTTP request
Backend-->>API : {items or data}
API-->>Page : result
Page->>Page : setData(recommendList, loading=false)
```

**Diagram sources**
- [pages/index/index.js:1-74](file://wechat-miniprogram/pages/index/index.js#L1-L74)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)

**Section sources**
- [pages/index/index.js:1-74](file://wechat-miniprogram/pages/index/index.js#L1-L74)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)

### Property Card Component
The property card component derives an image URL from the global baseUrl and emits tap events to parent pages.

```mermaid
classDiagram
class PropertyCard {
+Object property
+String coverUrl
+onTap()
}
class App {
+globalData.baseUrl
}
PropertyCard --> App : "reads baseUrl"
```

**Diagram sources**
- [components/property-card/property-card.js:1-30](file://wechat-miniprogram/components/property-card/property-card.js#L1-L30)
- [app.js:1-21](file://wechat-miniprogram/app.js#L1-L21)

**Section sources**
- [components/property-card/property-card.js:1-30](file://wechat-miniprogram/components/property-card/property-card.js#L1-L30)
- [app.js:1-21](file://wechat-miniprogram/app.js#L1-L21)

### Search Bar Component
The search bar component manages input binding and emits input/search events to parent pages.

```mermaid
classDiagram
class SearchBar {
+String value
+String placeholder
+onInput(e)
+onSearch()
}
```

**Diagram sources**
- [components/search-bar/search-bar.js:1-17](file://wechat-miniprogram/components/search-bar/search-bar.js#L1-L17)

**Section sources**
- [components/search-bar/search-bar.js:1-17](file://wechat-miniprogram/components/search-bar/search-bar.js#L1-L17)

### Map View Component
The map view component updates default markers when latitude and longitude change.

```mermaid
classDiagram
class MapView {
+Number latitude
+Number longitude
+Array markers
+Array defaultMarkers
}
MapView : "observers update defaultMarkers"
```

**Diagram sources**
- [components/map-view/map-view.js:1-29](file://wechat-miniprogram/components/map-view/map-view.js#L1-L29)

**Section sources**
- [components/map-view/map-view.js:1-29](file://wechat-miniprogram/components/map-view/map-view.js#L1-L29)

## Dependency Analysis
The mini program has clear dependency boundaries:
- Pages depend on utils/api.js and utils/auth.js.
- Components depend on app.js for global baseUrl.
- App depends on utils/auth.js for initial login checks.
- Configuration files define routing, DevTools behavior, and environment endpoints.

```mermaid
graph LR
App["app.js"] --> Auth["utils/auth.js"]
App --> API["utils/api.js"]
Index["pages/index/index.js"] --> API
Index --> Auth
PropCard["components/property-card/property-card.js"] --> App
SearchBar["components/search-bar/search-bar.js"] --> App
MapView["components/map-view/map-view.js"] --> App
Config["app.config.js"] --> API
Routing["app.json"] --> Index
DevCfg["project.config.json"] --> App
```

**Diagram sources**
- [app.js:1-21](file://wechat-miniprogram/app.js#L1-L21)
- [utils/auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [pages/index/index.js:1-74](file://wechat-miniprogram/pages/index/index.js#L1-L74)
- [components/property-card/property-card.js:1-30](file://wechat-miniprogram/components/property-card/property-card.js#L1-L30)
- [components/search-bar/search-bar.js:1-17](file://wechat-miniprogram/components/search-bar/search-bar.js#L1-L17)
- [components/map-view/map-view.js:1-29](file://wechat-miniprogram/components/map-view/map-view.js#L1-L29)
- [app.config.js:1-16](file://wechat-miniprogram/app.config.js#L1-L16)
- [app.json:1-57](file://wechat-miniprogram/app.json#L1-L57)
- [project.config.json:1-37](file://wechat-miniprogram/project.config.json#L1-L37)

**Section sources**
- [app.js:1-21](file://wechat-miniprogram/app.js#L1-L21)
- [utils/auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [pages/index/index.js:1-74](file://wechat-miniprogram/pages/index/index.js#L1-L74)
- [components/property-card/property-card.js:1-30](file://wechat-miniprogram/components/property-card/property-card.js#L1-L30)
- [components/search-bar/search-bar.js:1-17](file://wechat-miniprogram/components/search-bar/search-bar.js#L1-L17)
- [components/map-view/map-view.js:1-29](file://wechat-miniprogram/components/map-view/map-view.js#L1-L29)
- [app.config.js:1-16](file://wechat-miniprogram/app.config.js#L1-L16)
- [app.json:1-57](file://wechat-miniprogram/app.json#L1-L57)
- [project.config.json:1-37](file://wechat-miniprogram/project.config.json#L1-L37)

## Performance Considerations
- Prefer lazy loading and pagination for lists (e.g., use page/size parameters).
- Minimize setData payloads; update only changed fields.
- Use component observers judiciously to avoid excessive re-renders.
- Cache frequently accessed data in local storage where appropriate.
- Avoid heavy computations on the main thread; offload to background tasks if needed.
- Optimize images and assets; ensure correct paths derived from baseUrl.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- Network requests failing:
  - Verify baseUrl in app.config.js matches your running backend.
  - Ensure CORS is configured correctly on the backend for localhost during development.
  - Inspect network logs in DevTools to confirm request/response details.
- Token expiration (401):
  - The API wrapper clears stored tokens and resets global login state; trigger re-login via auth.checkLogin().
- Permission prompts:
  - Confirm requiredPrivateInfos and permission scopes in app.json align with feature needs (e.g., getLocation).
- DevTools configuration:
  - Ensure project.config.json settings match your development preferences (e.g., es6, postcss, uploadWithSourceMap).
- Sitemap rules:
  - Validate sitemap.json rules if indexing or SEO-related features are used.

Operational references:
- Local development quick start and mini program setup steps are documented in the root README.
- Production deployment and troubleshooting commands are provided in DEPLOYMENT.md.

**Section sources**
- [app.config.js:1-16](file://wechat-miniprogram/app.config.js#L1-L16)
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [app.json:1-57](file://wechat-miniprogram/app.json#L1-L57)
- [project.config.json:1-37](file://wechat-miniprogram/project.config.json#L1-L37)
- [sitemap.json:1-7](file://wechat-miniprogram/sitemap.json#L1-L7)
- [README.md:98-104](file://README.md#L98-L104)
- [DEPLOYMENT.md:112-134](file://DEPLOYMENT.md#L112-L134)

## Conclusion
This guide consolidates the development and debugging workflow for the WeChat Mini Program in this project. By leveraging the centralized API wrapper, robust authentication utility, and well-structured pages and components, developers can efficiently debug issues, optimize performance, and collaborate effectively. Following the outlined best practices and troubleshooting steps will streamline day-to-day development and reduce friction across the team.

[No sources needed since this section summarizes without analyzing specific files]

## Appendices

### WeChat DevTools Setup and Usage
- Open the wechat-miniprogram directory in WeChat DevTools.
- Set your AppID in project.config.json.
- Configure baseUrl and wsUrl in app.config.js for development or production.
- Enable source maps and ES6 support in project.config.json for better debugging experience.
- Use the Console panel to inspect logs and run snippets; use the Network panel to monitor requests; use the Performance panel to profile rendering and JS execution.

**Section sources**
- [project.config.json:1-37](file://wechat-miniprogram/project.config.json#L1-L37)
- [app.config.js:1-16](file://wechat-miniprogram/app.config.js#L1-L16)
- [README.md:98-104](file://README.md#L98-L104)

### Testing Strategies
- Unit testing:
  - For the mini program, unit tests typically target pure functions and utilities. In this repository, there are no dedicated mini program test files; consider adding tests for utils/api.js and utils/auth.js to validate request wrapping and login flows.
- Manual testing procedures:
  - Verify login flow end-to-end using DevTools.
  - Test network calls by toggling offline mode and checking error toasts.
  - Validate component behaviors (search input, property card tap, map marker updates) through interactive walkthroughs.

[No sources needed since this section provides general guidance]

### Code Organization Best Practices
- Keep business logic in utils and services; keep pages thin and focused on UI state.
- Centralize environment configuration in app.config.js.
- Use consistent naming and modularization for components and pages.
- Maintain clear separation between data fetching (api.js) and presentation (pages/components).

**Section sources**
- [utils/api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [utils/auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [app.config.js:1-16](file://wechat-miniprogram/app.config.js#L1-L16)
- [pages/index/index.js:1-74](file://wechat-miniprogram/pages/index/index.js#L1-L74)
- [components/property-card/property-card.js:1-30](file://wechat-miniprogram/components/property-card/property-card.js#L1-L30)
- [components/search-bar/search-bar.js:1-17](file://wechat-miniprogram/components/search-bar/search-bar.js#L1-L17)
- [components/map-view/map-view.js:1-29](file://wechat-miniprogram/components/map-view/map-view.js#L1-L29)

### Version Control and Collaboration Workflows
- Follow branch naming conventions and commit message formats as described in team documentation.
- Use GitHub Projects and labels to track tasks and automate workflow transitions.
- Ensure PRs include screenshots and CI passes before merging.

**Section sources**
- [README.md:22-62](file://README.md#L22-L62)
- [DEPLOYMENT.md:1-40](file://DEPLOYMENT.md#L1-L40)

### Hot Reloading and Efficient Debugging
- Hot reload is disabled by default in project.config.json; enable compileHotReLoad if desired for faster iteration.
- Use uploadWithSourceMap to improve stack traces in production builds.
- Leverage console logging strategically and avoid excessive logs in hot paths.

**Section sources**
- [project.config.json:1-37](file://wechat-miniprogram/project.config.json#L1-L37)