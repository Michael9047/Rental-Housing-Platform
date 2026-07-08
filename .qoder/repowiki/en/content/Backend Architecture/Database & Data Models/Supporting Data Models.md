# Supporting Data Models

<cite>
**Referenced Files in This Document**
- [contract.py](file://backend/app/models/contract.py)
- [payment.py](file://backend/app/models/payment.py)
- [notification.py](file://backend/app/models/notification.py)
- [chat.py](file://backend/app/models/chat.py)
- [poi.py](file://backend/app/models/poi.py)
- [mixins.py](file://backend/app/models/mixins.py)
- [contract_service.py](file://backend/app/services/contract_service.py)
- [payment_service.py](file://backend/app/services/payment_service.py)
- [notification_service.py](file://backend/app/services/notification_service.py)
- [poi_service.py](file://backend/app/services/poi_service.py)
- [contracts.py](file://backend/app/api/v1/routes/contracts.py)
- [payments.py](file://backend/app/api/v1/routes/payments.py)
- [notifications.py](file://backend/app/api/v1/routes/notifications.py)
- [pois.py](file://backend/app/api/v1/routes/pois.py)
- [contract.py](file://backend/app/schemas/contract.py)
- [payment.py](file://backend/app/schemas/payment.py)
- [notification.py](file://backend/app/schemas/notification.py)
- [poi.py](file://backend/app/schemas/poi.py)
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
This document describes the supporting data models and their usage patterns: Contract, Payment, Notification, Chat, and POI entities. It explains how these models integrate with core domain entities (Booking, User, Property), how they are exposed via APIs, and how services orchestrate business logic such as contract signing, payment processing, multi-channel notifications, AI chat sessions, and location-based point-of-interest generation.

## Project Structure
The supporting models live under backend/app/models and are paired with Pydantic schemas under backend/app/schemas and service implementations under backend/app/services. API routes under backend/app/api/v1/routes expose CRUD and workflow endpoints for each model.

```mermaid
graph TB
subgraph "Models"
M_Contract["Contract"]
M_Payment["Payment"]
M_Notification["Notification"]
M_ChatSession["ChatSession"]
M_ChatMessage["ChatMessage"]
M_PropertyPOI["PropertyPOI"]
M_Mixin["TimestampMixin"]
end
subgraph "Schemas"
S_Contract["ContractCreate / ContractResponse"]
S_Payment["PaymentCreate / PaymentResponse"]
S_Notification["NotificationRead / UnreadCount"]
S_POI["POIResponse"]
end
subgraph "Services"
SVC_Contract["ContractService"]
SVC_Payment["WeChatPayService"]
SVC_Notification["NotificationService"]
SVC_POI["POIService"]
end
subgraph "API Routes"
R_Contracts["/contracts/*"]
R_Payments["/payments/*"]
R_Notifications["/notifications/*"]
R_POIs["/pois/*"]
end
M_Contract --> M_Mixin
M_Payment --> M_Mixin
M_Notification --> M_Mixin
M_ChatSession --> M_Mixin
M_ChatMessage --> M_Mixin
M_PropertyPOI --> M_Mixin
R_Contracts --> SVC_Contract
R_Payments --> SVC_Payment
R_Notifications --> SVC_Notification
R_POIs --> SVC_POI
SVC_Contract --> M_Contract
SVC_Payment --> M_Payment
SVC_Notification --> M_Notification
SVC_POI --> M_PropertyPOI
S_Contract --> R_Contracts
S_Payment --> R_Payments
S_Notification --> R_Notifications
S_POI --> R_POIs
```

**Diagram sources**
- [contract.py:1-37](file://backend/app/models/contract.py#L1-L37)
- [payment.py:1-34](file://backend/app/models/payment.py#L1-L34)
- [notification.py:1-36](file://backend/app/models/notification.py#L1-L36)
- [chat.py:1-62](file://backend/app/models/chat.py#L1-L62)
- [poi.py:1-28](file://backend/app/models/poi.py#L1-L28)
- [mixins.py:1-19](file://backend/app/models/mixins.py#L1-L19)
- [contract_service.py:1-96](file://backend/app/services/contract_service.py#L1-L96)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)
- [notification_service.py:1-164](file://backend/app/services/notification_service.py#L1-L164)
- [poi_service.py:1-311](file://backend/app/services/poi_service.py#L1-L311)
- [contracts.py:1-88](file://backend/app/api/v1/routes/contracts.py#L1-L88)
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [notifications.py:1-50](file://backend/app/api/v1/routes/notifications.py#L1-L50)
- [pois.py:1-32](file://backend/app/api/v1/routes/pois.py#L1-L32)
- [contract.py:1-23](file://backend/app/schemas/contract.py#L1-L23)
- [payment.py:1-23](file://backend/app/schemas/payment.py#L1-L23)
- [notification.py:1-23](file://backend/app/schemas/notification.py#L1-L23)
- [poi.py:1-16](file://backend/app/schemas/poi.py#L1-L16)

**Section sources**
- [contract.py:1-37](file://backend/app/models/contract.py#L1-L37)
- [payment.py:1-34](file://backend/app/models/payment.py#L1-L34)
- [notification.py:1-36](file://backend/app/models/notification.py#L1-L36)
- [chat.py:1-62](file://backend/app/models/chat.py#L1-L62)
- [poi.py:1-28](file://backend/app/models/poi.py#L1-L28)
- [mixins.py:1-19](file://backend/app/models/mixins.py#L1-L19)
- [contract_service.py:1-96](file://backend/app/services/contract_service.py#L1-L96)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)
- [notification_service.py:1-164](file://backend/app/services/notification_service.py#L1-L164)
- [poi_service.py:1-311](file://backend/app/services/poi_service.py#L1-L311)
- [contracts.py:1-88](file://backend/app/api/v1/routes/contracts.py#L1-L88)
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [notifications.py:1-50](file://backend/app/api/v1/routes/notifications.py#L1-L50)
- [pois.py:1-32](file://backend/app/api/v1/routes/pois.py#L1-L32)
- [contract.py:1-23](file://backend/app/schemas/contract.py#L1-L23)
- [payment.py:1-23](file://backend/app/schemas/payment.py#L1-L23)
- [notification.py:1-23](file://backend/app/schemas/notification.py#L1-L23)
- [poi.py:1-16](file://backend/app/schemas/poi.py#L1-L16)

## Core Components
- Contract: Represents a rental agreement tied to a Booking, Tenant (User), and Property. Supports lifecycle states (draft, signed), optional file storage path, and timestamping.
- Payment: Tracks deposit or rent payments linked to a Booking and User, including transaction identifiers, status, method, and timestamps.
- Notification: Stores user-targeted messages with typed categories and read/unread state; integrates with multi-channel delivery via Celery tasks.
- Chat: Manages conversational sessions and messages with roles (user, assistant, system) and JSON metadata for context.
- POI: Associates generated points-of-interest content and structured category data with a Property, including review flags and generation timestamps.

All models inherit TimestampMixin for created_at and updated_at fields.

**Section sources**
- [contract.py:1-37](file://backend/app/models/contract.py#L1-L37)
- [payment.py:1-34](file://backend/app/models/payment.py#L1-L34)
- [notification.py:1-36](file://backend/app/models/notification.py#L1-L36)
- [chat.py:1-62](file://backend/app/models/chat.py#L1-L62)
- [poi.py:1-28](file://backend/app/models/poi.py#L1-L28)
- [mixins.py:1-19](file://backend/app/models/mixins.py#L1-L19)

## Architecture Overview
The supporting models are accessed through FastAPI routes that delegate to service classes. Services perform database operations, external integrations (e.g., WeChat Pay, AMap geocoding, OpenAI), and orchestration across related entities. Notifications use asynchronous task dispatch for email, SMS, and WeChat channels.

```mermaid
sequenceDiagram
participant Client as "Client"
participant API as "FastAPI Route"
participant Service as "Service Layer"
participant DB as "Database"
participant External as "External Services"
Client->>API : "POST /contracts/{booking_id}/generate"
API->>Service : "ContractService.generate_contract(booking)"
Service->>DB : "Load Booking/User/Property"
DB-->>Service : "Entities"
Service->>DB : "Persist Contract (draft)"
DB-->>Service : "Contract"
Service-->>API : "ContractResponse"
API-->>Client : "201 Created"
Client->>API : "POST /payments/create"
API->>Service : "WeChatPayService.create_jsapi_order(...)"
Service->>External : "WeChat Pay JSAPI order"
External-->>Service : "prepay_id"
Service->>DB : "Persist Payment (pending)"
DB-->>Service : "Payment"
Service-->>API : "PaymentResponse"
API-->>Client : "201 Created"
Client->>API : "GET /notifications"
API->>Service : "NotificationService.list_by_user(user_id)"
Service->>DB : "Query notifications"
DB-->>Service : "List"
Service-->>API : "Notifications"
API-->>Client : "200 OK"
Client->>API : "POST /pois/{property_id}/generate"
API->>Service : "POIService.get_or_generate_poi(property_id)"
Service->>DB : "Check existing POI"
alt "Not found"
Service->>External : "AMap nearby search + OpenAI summary"
External-->>Service : "Categories + Summary"
Service->>DB : "Create PropertyPOI"
end
Service-->>API : "POIResponse"
API-->>Client : "201 Created"
```

**Diagram sources**
- [contracts.py:1-88](file://backend/app/api/v1/routes/contracts.py#L1-L88)
- [contract_service.py:1-96](file://backend/app/services/contract_service.py#L1-L96)
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)
- [notifications.py:1-50](file://backend/app/api/v1/routes/notifications.py#L1-L50)
- [notification_service.py:1-164](file://backend/app/services/notification_service.py#L1-L164)
- [pois.py:1-32](file://backend/app/api/v1/routes/pois.py#L1-L32)
- [poi_service.py:1-311](file://backend/app/services/poi_service.py#L1-L311)

## Detailed Component Analysis

### Contract Model
- Purpose: Store legal rental agreements per booking with template name, content, status, signature time, and optional file path.
- Relationships:
  - booking_id -> Bookings (unique)
  - tenant_id -> Users
  - property_id -> Properties
- Lifecycle:
  - Draft creation from booking details
  - Signing by tenant updates status and signed_at
- Digital Signature Support:
  - The model includes signed_at and file_path fields suitable for storing signature artifacts and signed documents.
  - The sign endpoint enforces tenant-only signing and prevents double-signing.
- Template Management:
  - template_name field supports selecting different contract templates.
  - Generation populates content based on booking and property data.

```mermaid
classDiagram
class Contract {
+string id
+int booking_id
+int tenant_id
+int property_id
+string template_name
+string content
+string status
+datetime signed_at
+string file_path
+created_at
+updated_at
}
class Booking
class User
class Property
Contract --> Booking : "booking_id"
Contract --> User : "tenant_id"
Contract --> Property : "property_id"
```

**Diagram sources**
- [contract.py:1-37](file://backend/app/models/contract.py#L1-L37)

```mermaid
flowchart TD
Start(["Generate Contract"]) --> CheckExisting["Check if contract exists for booking"]
CheckExisting --> |Exists| Conflict["Return conflict error"]
CheckExisting --> |Not Exists| LoadData["Load Booking, User, Property"]
LoadData --> BuildContent["Build contract content from data"]
BuildContent --> Persist["Persist Contract (status=draft)"]
Persist --> End(["Return Contract"])
```

**Diagram sources**
- [contract_service.py:1-96](file://backend/app/services/contract_service.py#L1-L96)
- [contracts.py:1-88](file://backend/app/api/v1/routes/contracts.py#L1-L88)

**Section sources**
- [contract.py:1-37](file://backend/app/models/contract.py#L1-L37)
- [contract_service.py:1-96](file://backend/app/services/contract_service.py#L1-L96)
- [contracts.py:1-88](file://backend/app/api/v1/routes/contracts.py#L1-L88)
- [contract.py:1-23](file://backend/app/schemas/contract.py#L1-L23)

### Payment Model
- Purpose: Track financial transactions for bookings, including amount, method, status, and timestamps.
- Relationships:
  - booking_id -> Bookings
  - user_id -> Users
- Transaction Tracking:
  - transaction_id links to external payment provider records.
  - status transitions from pending to success upon callback confirmation.
- Payment Method Integration:
  - Default method is wechat_pay; WeChat Pay V3 integration handles order creation, signature verification, decryption, and refund flows.
- Financial Reconciliation:
  - Callbacks update payment.paid_at and booking.deposit_status to confirmed.
  - Query endpoints support reconciliation by out_trade_no or transaction_id.

```mermaid
classDiagram
class Payment {
+string id
+int booking_id
+int user_id
+int amount
+string transaction_id
+string status
+string payment_method
+datetime paid_at
+created_at
+updated_at
}
class Booking
class User
Payment --> Booking : "booking_id"
Payment --> User : "user_id"
```

**Diagram sources**
- [payment.py:1-34](file://backend/app/models/payment.py#L1-L34)

```mermaid
sequenceDiagram
participant Client as "Mini Program"
participant API as "Payments Route"
participant PaySvc as "WeChatPayService"
participant WX as "WeChat Pay API"
participant DB as "Database"
Client->>API : "POST /payments/create"
API->>DB : "Create Payment (pending)"
API->>PaySvc : "create_jsapi_order(out_trade_no, openid, amount, description)"
PaySvc->>WX : "JSAPI order request"
WX-->>PaySvc : "prepay_id"
PaySvc-->>API : "JsapiOrderResult"
API-->>Client : "PaymentResponse"
WX-->>API : "Callback (signature + encrypted resource)"
API->>PaySvc : "parse_callback(headers, body)"
PaySvc->>PaySvc : "Verify signature + decrypt resource"
PaySvc-->>API : "CallbackResult"
API->>DB : "Update Payment.status=success, paid_at"
API->>DB : "Update Booking.deposit_status=confirmed"
API-->>Client : "PaymentResponse"
```

**Diagram sources**
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)

**Section sources**
- [payment.py:1-34](file://backend/app/models/payment.py#L1-L34)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [payment.py:1-23](file://backend/app/schemas/payment.py#L1-L23)

### Notification Model
- Purpose: Deliver system and event-driven messages to users with typed categories and read/unread tracking.
- Multi-channel Delivery:
  - Channels include WeChat template messages, SMS, and Email.
  - Dispatch uses Celery tasks; failures are logged without blocking DB writes.
- User Preferences:
  - Channel selection can be specified per notification; defaults to all channels.
- Read State Management:
  - Mark single or all notifications as read; provide unread count.

```mermaid
classDiagram
class Notification {
+int id
+int user_id
+enum type
+string title
+string content
+bool is_read
+created_at
+updated_at
}
class User
Notification --> User : "user_id"
```

**Diagram sources**
- [notification.py:1-36](file://backend/app/models/notification.py#L1-L36)

```mermaid
sequenceDiagram
participant Client as "Client"
participant API as "Notifications Route"
participant NotifSvc as "NotificationService"
participant Tasks as "Celery Tasks"
participant DB as "Database"
Client->>API : "GET /notifications"
API->>NotifSvc : "list_by_user(user_id)"
NotifSvc->>DB : "Select notifications"
DB-->>NotifSvc : "List"
NotifSvc-->>API : "Notifications"
API-->>Client : "200 OK"
Note over NotifSvc,Tasks : "On create_notification, fire-and-forget channel dispatch"
```

**Diagram sources**
- [notifications.py:1-50](file://backend/app/api/v1/routes/notifications.py#L1-L50)
- [notification_service.py:1-164](file://backend/app/services/notification_service.py#L1-L164)

**Section sources**
- [notification.py:1-36](file://backend/app/models/notification.py#L1-L36)
- [notification_service.py:1-164](file://backend/app/services/notification_service.py#L1-L164)
- [notifications.py:1-50](file://backend/app/api/v1/routes/notifications.py#L1-L50)
- [notification.py:1-23](file://backend/app/schemas/notification.py#L1-L23)

### Chat Model
- Purpose: Manage AI assistant conversations with session scoping and message history.
- Context Management:
  - ChatSession groups messages and tracks status (active/closed).
  - ChatMessage stores role (user/assistant/system), content, and JSON metadata for context.
- Usage Patterns:
  - Create a new session per conversation thread.
  - Append messages with role and optional metadata (e.g., tool calls, references).
  - Close sessions when appropriate to free resources.

```mermaid
classDiagram
class ChatSession {
+int id
+int user_id
+string session_id
+string title
+enum status
+created_at
+updated_at
}
class ChatMessage {
+int id
+int session_id
+enum role
+string content
+dict metadata_
+created_at
+updated_at
}
class User
ChatSession --> User : "user_id"
ChatMessage --> ChatSession : "session_id"
```

**Diagram sources**
- [chat.py:1-62](file://backend/app/models/chat.py#L1-L62)

**Section sources**
- [chat.py:1-62](file://backend/app/models/chat.py#L1-L62)

### POI Model
- Purpose: Provide location-based insights for properties, including summarized descriptions and categorized nearby facilities.
- Features:
  - Content summary and structured poi_data (categories like transport, dining, shopping).
  - generated_at timestamp and reviewed flag for moderation workflows.
- Generation Logic:
  - Uses AMap geocoding and nearby search to collect facilities.
  - Optional OpenAI summarization to produce natural language summaries.
  - Fallback to mock data when external services fail.

```mermaid
classDiagram
class PropertyPOI {
+string id
+int property_id
+string content
+dict poi_data
+datetime generated_at
+bool reviewed
+created_at
+updated_at
}
class Property
PropertyPOI --> Property : "property_id"
```

**Diagram sources**
- [poi.py:1-28](file://backend/app/models/poi.py#L1-L28)

```mermaid
flowchart TD
Start(["Get or Generate POI"]) --> CheckExisting["Check PropertyPOI by property_id"]
CheckExisting --> |Found| ReturnPOI["Return existing POI"]
CheckExisting --> |Not Found| ResolveLocation["Resolve coordinates (direct or geocode)"]
ResolveLocation --> CollectNearby["Search nearby categories via AMap"]
CollectNearby --> ComposeSummary["Compose summary (OpenAI or deterministic)"]
ComposeSummary --> PersistPOI["Create/Update PropertyPOI"]
PersistPOI --> ReturnPOI
```

**Diagram sources**
- [poi_service.py:1-311](file://backend/app/services/poi_service.py#L1-L311)
- [pois.py:1-32](file://backend/app/api/v1/routes/pois.py#L1-L32)

**Section sources**
- [poi.py:1-28](file://backend/app/models/poi.py#L1-L28)
- [poi_service.py:1-311](file://backend/app/services/poi_service.py#L1-L311)
- [pois.py:1-32](file://backend/app/api/v1/routes/pois.py#L1-L32)
- [poi.py:1-16](file://backend/app/schemas/poi.py#L1-L16)

## Dependency Analysis
- Model Dependencies:
  - All models depend on TimestampMixin for auditability.
  - Contract depends on Booking, User, Property.
  - Payment depends on Booking, User.
  - Notification depends on User.
  - ChatSession depends on User; ChatMessage depends on ChatSession.
  - PropertyPOI depends on Property.
- Service Dependencies:
  - ContractService orchestrates Booking/User/Property reads and Contract persistence.
  - WeChatPayService integrates with WeChat Pay V3 for order creation, callbacks, refunds.
  - NotificationService dispatches async tasks for multiple channels.
  - POIService integrates AMap geocoding and optional OpenAI summarization.

```mermaid
graph TB
Contract["Contract"] --> Booking["Booking"]
Contract --> User["User"]
Contract --> Property["Property"]
Payment["Payment"] --> Booking
Payment --> User
Notification["Notification"] --> User
ChatSession["ChatSession"] --> User
ChatMessage["ChatMessage"] --> ChatSession
PropertyPOI["PropertyPOI"] --> Property
```

**Diagram sources**
- [contract.py:1-37](file://backend/app/models/contract.py#L1-L37)
- [payment.py:1-34](file://backend/app/models/payment.py#L1-L34)
- [notification.py:1-36](file://backend/app/models/notification.py#L1-L36)
- [chat.py:1-62](file://backend/app/models/chat.py#L1-L62)
- [poi.py:1-28](file://backend/app/models/poi.py#L1-L28)

**Section sources**
- [contract.py:1-37](file://backend/app/models/contract.py#L1-L37)
- [payment.py:1-34](file://backend/app/models/payment.py#L1-L34)
- [notification.py:1-36](file://backend/app/models/notification.py#L1-L36)
- [chat.py:1-62](file://backend/app/models/chat.py#L1-L62)
- [poi.py:1-28](file://backend/app/models/poi.py#L1-L28)

## Performance Considerations
- Indexing:
  - Contracts and Payments index foreign keys for efficient lookups.
  - Notifications index user_id and id for listing and marking read.
  - ChatSession indexes user_id and session_id for session retrieval.
- Eager Loading:
  - ChatSession relationship uses selectin loading to reduce N+1 queries when fetching messages.
- Asynchronous Operations:
  - Notification channel dispatch is fire-and-forget via Celery to avoid blocking response times.
- External Integrations:
  - POI generation may involve multiple AMap calls and optional OpenAI requests; fallback mechanisms ensure resilience.
- Payment Callbacks:
  - Signature verification and AES-GCM decryption should be optimized; consider caching platform certificates and minimizing redundant I/O.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
- Contract Issues:
  - Duplicate contract generation: Ensure generate endpoint checks for existing contracts per booking.
  - Unauthorized signing: Verify tenant ownership before updating status and signed_at.
- Payment Issues:
  - Callback signature verification: Confirm headers and payload structure; ensure APIv3 key and private key paths are correct.
  - Order query mismatches: Validate out_trade_no and transaction_id mapping to Payment records.
- Notification Issues:
  - Channel dispatch failures: Inspect Celery worker logs; verify task imports and credentials for SMS/email/WeChat.
  - Read state inconsistencies: Ensure mark_read and mark_all_read operate within proper authorization boundaries.
- POI Issues:
  - Geocoding failures: Fall back to district-based mock data; log warnings and retry strategies.
  - OpenAI summarization errors: Use deterministic summary fallback; validate JSON response parsing.

**Section sources**
- [contracts.py:1-88](file://backend/app/api/v1/routes/contracts.py#L1-L88)
- [contract_service.py:1-96](file://backend/app/services/contract_service.py#L1-L96)
- [payments.py:1-85](file://backend/app/api/v1/routes/payments.py#L1-L85)
- [payment_service.py:1-445](file://backend/app/services/payment_service.py#L1-L445)
- [notifications.py:1-50](file://backend/app/api/v1/routes/notifications.py#L1-L50)
- [notification_service.py:1-164](file://backend/app/services/notification_service.py#L1-L164)
- [pois.py:1-32](file://backend/app/api/v1/routes/pois.py#L1-L32)
- [poi_service.py:1-311](file://backend/app/services/poi_service.py#L1-L311)

## Conclusion
The supporting data models provide robust foundations for legal agreements, financial transactions, user notifications, AI-assisted conversations, and location-based insights. Their design emphasizes clear relationships, extensibility, and operational resilience through asynchronous processing and fallback strategies. Proper indexing, eager loading, and secure integrations ensure performance and reliability at scale.

[No sources needed since this section summarizes without analyzing specific files]