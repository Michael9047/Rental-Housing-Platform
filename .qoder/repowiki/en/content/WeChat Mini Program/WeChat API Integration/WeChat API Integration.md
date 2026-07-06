# WeChat API Integration

<cite>
**Referenced Files in This Document**
- [app.js](file://wechat-miniprogram/app.js)
- [auth.js](file://wechat-miniprogram/utils/auth.js)
- [api.js](file://wechat-miniprogram/utils/api.js)
- [app.json](file://wechat-miniprogram/app.json)
- [map-view.wxml](file://wechat-miniprogram/components/map-view/map-view.wxml)
- [me.wxml](file://wechat-miniprogram/pages/me/me.wxml)
- [me.js](file://wechat-miniprogram/pages/me/me.js)
- [property.js](file://wechat-miniprogram/pages/property/property.js)
- [chat.js](file://wechat-miniprogram/pages/chat/chat.js)
- [wechat.py](file://backend/app/api/v1/routes/wechat.py)
- [wechat_service.py](file://backend/app/services/wechat_service.py)
- [payments.py](file://backend/app/api/v1/routes/payments.py)
- [payment_service.py](file://backend/app/services/payment_service.py)
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

## Introduction
This document explains how the mini program integrates with WeChat APIs and backend services to implement authentication, phone number binding, location services, payment processing, and common WeChat features such as sharing, scanning, and file uploads. It focuses on the end-to-end flows from the mini program UI through the backend to WeChat platforms, including error handling, security considerations, and practical implementation references.

## Project Structure
The integration spans two layers:
- Mini program (frontend): Handles user interactions, calls WeChat native APIs, and communicates with the backend via HTTP.
- Backend (Python/FastAPI): Exposes REST endpoints for login, phone binding, payments, and configuration; interacts with WeChat Open Platform and WeChat Pay V3.

```mermaid
graph TB
subgraph "Mini Program"
A["app.js"]
B["utils/auth.js"]
C["utils/api.js"]
D["pages/me/me.wxml + me.js"]
E["components/map-view/map-view.wxml"]
F["pages/property/property.js"]
G["pages/chat/chat.js"]
end
subgraph "Backend"
H["routes/wechat.py"]
I["services/wechat_service.py"]
J["routes/payments.py"]
K["services/payment_service.py"]
end
subgraph "WeChat Platforms"
L["Open Platform APIs"]
M["WeChat Pay V3"]
end
A --> B
B --> C
D --> B
D --> C
E --> C
F --> C
G --> C
C --> H
C --> J
H --> I
J --> K
I --> L
K --> M
```

**Diagram sources**
- [app.js:1-21](file://wechat-miniprogram/app.js#L1-L21)
- [auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [me.wxml:1-30](file://wechat-miniprogram/pages/me/me.wxml#L1-L30)
- [me.js:1-60](file://wechat-miniprogram/pages/me/me.js#L1-L60)
- [map-view.wxml:1-9](file://wechat-miniprogram/components/map-view/map-view.wxml#L1-L9)
- [property.js:1-90](file://wechat-miniprogram/pages/property/property.js#L1-L90)
- [chat.js:53-107](file://wechat-miniprogram/pages/chat/chat.js#L53-L107)
- [wechat.py:1-82](file://backend/app/api/v1/routes/wechat.py#L1-L82)
- [wechat_service.py:1-146](file://backend/app/services/wechat_service.py#L1-L146)
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)

**Section sources**
- [app.js:1-21](file://wechat-miniprogram/app.js#L1-L21)
- [app.json:1-57](file://wechat-miniprogram/app.json#L1-L57)

## Core Components
- Authentication flow: wx.login -> backend code-to-session exchange -> JWT issuance and storage.
- Phone binding: getPhoneNumber button -> backend exchanges code for phone number -> persists to user profile.
- Location services: permission declaration and map component usage.
- Payment processing: JSAPI order creation, signature building, and callback verification.
- Network layer: centralized request wrapper with token injection and error handling.

**Section sources**
- [auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [wechat.py:1-82](file://backend/app/api/v1/routes/wechat.py#L1-L82)
- [wechat_service.py:1-146](file://backend/app/services/wechat_service.py#L1-L146)
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)
- [app.json:48-53](file://wechat-miniprogram/app.json#L48-L53)
- [map-view.wxml:1-9](file://wechat-miniprogram/components/map-view/map-view.wxml#L1-L9)

## Architecture Overview
End-to-end flows for key features:

```mermaid
sequenceDiagram
participant MP as "Mini Program<br/>auth.js"
participant API as "Mini API Wrapper<br/>api.js"
participant BE as "Backend Route<br/>routes/wechat.py"
participant WS as "WeChat Service<br/>services/wechat_service.py"
participant WX as "WeChat Open Platform"
MP->>MP : "wx.login()"
MP->>API : "POST /wechat/auth/wechat/login {code}"
API->>BE : "HTTP POST"
BE->>WS : "jscode2session(code)"
WS->>WX : "GET sns/jscode2session"
WX-->>WS : "{openid, session_key, unionid?}"
WS-->>BE : "WeChatSession"
BE-->>API : "{access_token, user}"
API-->>MP : "Store token and user"
```

**Diagram sources**
- [auth.js:9-33](file://wechat-miniprogram/utils/auth.js#L9-L33)
- [api.js:4-41](file://wechat-miniprogram/utils/api.js#L4-L41)
- [wechat.py:19-38](file://backend/app/api/v1/routes/wechat.py#L19-L38)
- [wechat_service.py:45-65](file://backend/app/services/wechat_service.py#L45-L65)

## Detailed Component Analysis

### Authentication Flow (wx.login and code-to-session)
- The mini program obtains a temporary login code via wx.login and sends it to the backend.
- The backend exchanges the code for openid and session_key using the WeChat Open Platform API.
- The backend issues an access token and returns user info to the mini program, which stores them locally.

```mermaid
flowchart TD
Start(["Start Login"]) --> GetCode["Call wx.login()"]
GetCode --> HasCode{"Has code?"}
HasCode --> |No| Fail["Reject with error"]
HasCode --> |Yes| PostLogin["POST /wechat/auth/wechat/login"]
PostLogin --> Exchange["Backend jscode2session()"]
Exchange --> Token["Issue JWT and return user"]
Token --> Store["Store access_token and user"]
Store --> Done(["Logged in"])
```

**Diagram sources**
- [auth.js:9-33](file://wechat-miniprogram/utils/auth.js#L9-L33)
- [wechat.py:19-38](file://backend/app/api/v1/routes/wechat.py#L19-L38)
- [wechat_service.py:45-65](file://backend/app/services/wechat_service.py#L45-L65)

**Section sources**
- [auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [wechat.py:1-82](file://backend/app/api/v1/routes/wechat.py#L1-L82)
- [wechat_service.py:1-146](file://backend/app/services/wechat_service.py#L1-L146)

### Phone Number Binding (getPhoneNumber)
- The “Bind phone number” button uses open-type="getPhoneNumber" to obtain a one-time code.
- The mini program posts this code to the backend, which calls WeChat’s getuserphonenumber API to retrieve the phone number and updates the user record.

```mermaid
sequenceDiagram
participant UI as "me.wxml"
participant Page as "me.js"
participant API as "api.js"
participant BE as "routes/wechat.py"
participant WS as "services/wechat_service.py"
participant WX as "WeChat Open Platform"
UI->>Page : "bindgetphonenumber event"
Page->>API : "POST /auth/wechat/phone {code}"
API->>BE : "HTTP POST"
BE->>WS : "get_access_token()"
WS-->>BE : "access_token"
BE->>WX : "POST business/getuserphonenumber"
WX-->>BE : "{phone_info}"
BE-->>API : "{phone}"
API-->>Page : "Success"
```

**Diagram sources**
- [me.wxml:27-29](file://wechat-miniprogram/pages/me/me.wxml#L27-L29)
- [me.js:44-60](file://wechat-miniprogram/pages/me/me.js#L44-L60)
- [wechat.py:41-74](file://backend/app/api/v1/routes/wechat.py#L41-L74)
- [wechat_service.py:67-88](file://backend/app/services/wechat_service.py#L67-L88)

**Section sources**
- [me.wxml:1-30](file://wechat-miniprogram/pages/me/me.wxml#L1-L30)
- [me.js:1-60](file://wechat-miniprogram/pages/me/me.js#L1-L60)
- [wechat.py:41-74](file://backend/app/api/v1/routes/wechat.py#L41-L74)
- [wechat_service.py:67-88](file://backend/app/services/wechat_service.py#L67-L88)

### Location Services Integration
- Permission is declared in app.json for scope.userLocation and requiredPrivateInfos includes getLocation.
- The map component displays current location and markers.

```mermaid
flowchart TD
Init["App Launch"] --> CheckPerm["Check permissions in app.json"]
CheckPerm --> UseMap["Render map-view component"]
UseMap --> ShowLoc["show-location enabled"]
ShowLoc --> End(["Display nearby properties"])
```

**Diagram sources**
- [app.json:48-53](file://wechat-miniprogram/app.json#L48-L53)
- [map-view.wxml:1-9](file://wechat-miniprogram/components/map-view/map-view.wxml#L1-L9)

**Section sources**
- [app.json:48-53](file://wechat-miniprogram/app.json#L48-L53)
- [map-view.wxml:1-9](file://wechat-miniprogram/components/map-view/map-view.wxml#L1-L9)

### Payment Processing Integration (JSAPI)
- The backend creates a JSAPI prepay order and builds parameters for wx.requestPayment().
- After payment, WeChat Pay sends a callback that must be verified and decrypted before updating records.

```mermaid
sequenceDiagram
participant FE as "Mini Program"
participant BE as "routes/payments.py"
participant PS as "services/payment_service.py"
participant WXP as "WeChat Pay V3"
FE->>BE : "POST /payments/create"
BE->>PS : "create_jsapi_order(out_trade_no, openid, amount)"
PS->>WXP : "POST /v3/pay/transactions/jsapi"
WXP-->>PS : "{prepay_id}"
PS-->>BE : "JsapiOrderResult"
BE-->>FE : "Prepay params for wx.requestPayment()"
FE->>WXP : "wx.requestPayment(params)"
WXP-->>BE : "Callback with signature and encrypted resource"
BE->>PS : "parse_callback(headers, body)"
PS-->>BE : "CallbackResult"
BE-->>FE : "Update status and respond"
```

**Diagram sources**
- [payments.py:15-45](file://backend/app/api/v1/routes/payments.py#L15-L45)
- [payment_service.py:245-323](file://backend/app/services/payment_service.py#L245-L323)
- [payment_service.py:325-377](file://backend/app/services/payment_service.py#L325-L377)

**Section sources**
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)

### Network Request Layer and Error Handling
- The request wrapper injects Authorization headers when available and handles 401 by clearing local tokens.
- Non-2xx responses show toast messages and reject with structured errors.

```mermaid
flowchart TD
Req["api.get/post/..."] --> BuildHeader["Attach Authorization if present"]
BuildHeader --> Call["wx.request(...)"]
Call --> Ok{"Status 2xx?"}
Ok --> |Yes| Resolve["Resolve with data"]
Ok --> |No| Code401{"Status 401?"}
Code401 --> |Yes| Clear["Clear token and user"]
Clear --> Reject401["Reject with 401"]
Code401 --> |No| Toast["Show toast with detail"]
Toast --> RejectErr["Reject with response"]
```

**Diagram sources**
- [api.js:4-41](file://wechat-miniprogram/utils/api.js#L4-L41)

**Section sources**
- [api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)

### WeChat-Specific Features Examples
- Sharing: Implement via onShareAppMessage/onShareTimeline handlers in page lifecycle methods.
- Scanning: Use wx.scanCode to read QR/barcodes and navigate or submit results.
- File uploads: Use wx.chooseMedia/wx.chooseImage to select files, then upload via multipart/form-data to the backend upload endpoint.

[No sources needed since this section provides general guidance]

## Dependency Analysis
Key dependencies between modules:

```mermaid
graph LR
Auth["utils/auth.js"] --> Api["utils/api.js"]
MeUI["pages/me/me.wxml"] --> MeJS["pages/me/me.js"]
MeJS --> Api
MapView["components/map-view/map-view.wxml"] --> Api
Property["pages/property/property.js"] --> Api
Chat["pages/chat/chat.js"] --> Api
Api --> WechatRoute["routes/wechat.py"]
Api --> PaymentsRoute["routes/payments.py"]
WechatRoute --> WechatSvc["services/wechat_service.py"]
PaymentsRoute --> PaySvc["services/payment_service.py"]
```

**Diagram sources**
- [auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [me.wxml:1-30](file://wechat-miniprogram/pages/me/me.wxml#L1-L30)
- [me.js:1-60](file://wechat-miniprogram/pages/me/me.js#L1-L60)
- [map-view.wxml:1-9](file://wechat-miniprogram/components/map-view/map-view.wxml#L1-L9)
- [property.js:1-90](file://wechat-miniprogram/pages/property/property.js#L1-L90)
- [chat.js:53-107](file://wechat-miniprogram/pages/chat/chat.js#L53-L107)
- [wechat.py:1-82](file://backend/app/api/v1/routes/wechat.py#L1-L82)
- [wechat_service.py:1-146](file://backend/app/services/wechat_service.py#L1-L146)
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)

**Section sources**
- [auth.js:1-81](file://wechat-miniprogram/utils/auth.js#L1-L81)
- [api.js:1-52](file://wechat-miniprogram/utils/api.js#L1-L52)
- [wechat.py:1-82](file://backend/app/api/v1/routes/wechat.py#L1-L82)
- [wechat_service.py:1-146](file://backend/app/services/wechat_service.py#L1-L146)
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)

## Performance Considerations
- Cache WeChat access tokens server-side with expiration checks to reduce external calls.
- Minimize network requests by batching operations where possible.
- Use lazy loading for images and defer heavy computations until needed.
- For payments, ensure idempotency keys (out_trade_no) are unique and persisted to avoid duplicate charges.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- 401 Unauthorized: The request wrapper clears tokens and prompts re-login. Ensure the backend validates tokens and refreshes sessions appropriately.
- Phone binding failures: Verify the ephemeral code is used once and within its validity window; check backend logs for WeChat API errcode.
- Payment callbacks not processed: Confirm signature verification and AES-GCM decryption steps; validate timestamps and nonces.
- Location permission denied: Ensure app.json declares scope.userLocation and requiredPrivateInfos; prompt users to enable location in system settings.

**Section sources**
- [api.js:22-38](file://wechat-miniprogram/utils/api.js#L22-L38)
- [wechat.py:60-74](file://backend/app/api/v1/routes/wechat.py#L60-L74)
- [payment_service.py:325-377](file://backend/app/services/payment_service.py#L325-L377)
- [app.json:48-53](file://wechat-miniprogram/app.json#L48-L53)

## Conclusion
The mini program integrates WeChat Open Platform and WeChat Pay V3 through a clear separation of concerns: the frontend handles UX and native APIs, while the backend manages secure exchanges, signatures, and state persistence. Following the documented flows and security practices ensures robust authentication, phone binding, location display, and reliable payment processing.