# Rental Housing Frontend

Vue 3 + TypeScript + Vite 前端应用，为租房匹配系统提供用户界面。

## Tech Stack

- **Vue 3** - Composition API + <script setup>
- **TypeScript** - 类型安全
- **Vite** - 开发与构建工具
- **Vue Router 4** - 路由管理
- **Pinia** - 状态管理
- **Axios** - HTTP 请求
- **Element Plus** - UI 组件库

## Project Structure

`
frontend/
├── public/                 # Static assets
├── src/
│   ├── components/         # Reusable components
│   │   ├── PropertyCard.vue
│   │   └── SearchBar.vue
│   ├── layouts/
│   │   └── DefaultLayout.vue  # App shell (nav + sidebar + main)
│   ├── router/
│   │   └── index.ts        # Routes + navigation guards
│   ├── services/
│   │   ├── api.ts           # Axios instance + interceptors
│   │   ├── auth.ts          # Auth API calls
│   │   ├── property.ts      # Property API calls
│   │   └── user.ts          # User API calls
│   ├── stores/
│   │   ├── auth.ts          # Auth state (Pinia)
│   │   └── property.ts      # Property state (Pinia)
│   ├── types/
│   │   ├── auth.ts          # Auth type definitions
│   │   ├── property.ts      # Property type definitions
│   │   └── user.ts          # User type definitions
│   ├── views/
│   │   ├── Home.vue         # Landing page
│   │   ├── Search.vue       # Property search & filters
│   │   ├── PropertyDetail.vue  # Single property view
│   │   ├── Login.vue        # Login form
│   │   ├── Register.vue     # Registration form
│   │   ├── Profile.vue      # User profile
│   │   ├── CreateProperty.vue  # Publish property form
│   │   └── ManageProperties.vue # Landlord property management
│   ├── App.vue
│   └── main.ts
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.app.json
├── vite.config.ts
└── env.d.ts
`

## Quick Start

`ash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start dev server (http://localhost:5173)
npm run dev

# Build for production
npm run build
`

The dev server proxies /api requests to the backend at http://localhost:8000.

## Map Integration

房源详情页支持高德地图嵌入展示。若要启用真实地图，请在前端环境变量中配置：

- `VITE_AMAP_KEY` - 高德地图 Web 端 JS API Key
- `VITE_AMAP_SECURITY_JS_CODE` - 可选，用于需要安全密钥的场景

未配置时，页面会自动降级为高德地图外链查看，不影响房源详情页使用。

## Routes

| Path | Name | Auth | Description |
|------|------|------|-------------|
| / | home | No | Landing page with quick search |
| /search | search | No | Property search with filters |
| /property/:id | property-detail | No | Property detail view |
| /login | login | Guest only | Login form |
| /register | register | Guest only | Registration form |
| /profile | profile | Required | User profile & edit |
| /property/create | create-property | Landlord/Admin | Publish new property |
| /property/manage | manage-properties | Landlord/Admin | Manage own properties |

## Backend API Mapping

All API calls go through /api/v1/:

- POST /auth/register - User registration
- POST /auth/login - User login (returns JWT)
- GET /auth/me - Current user info
- GET /users/me - Get profile
- PATCH /users/me - Update profile
- GET /properties - List properties
- POST /properties - Create property (landlord)
- GET /properties/search - Search properties
- GET /properties/:id - Get property
- PATCH /properties/:id - Update property (owner/admin)
- DELETE /properties/:id - Delete property (owner/admin)

## Phase 6: Property Images

### Pages
- **PropertyImages** (`/property/:id/images`) - Image management: upload, preview, set cover, delete
- Property detail pages now show image carousel (`el-carousel`)
- Property cards display the primary image (or placeholder if none)

### Components Updated
- `PropertyCard.vue` - Shows primary image instead of placeholder
- `PropertyDetail.vue` - Image gallery with carousel and preview
- `ManageProperties.vue` - Added "Manage Images" button
- `CreateProperty.vue` - Redirects to image upload after creation

### Services
- `propertyService.listImages(propertyId)`
- `propertyService.uploadImages(propertyId, files)` (multipart/form-data)
- `propertyService.deleteImage(propertyId, imageId)`
- `propertyService.setPrimaryImage(propertyId, imageId)`
