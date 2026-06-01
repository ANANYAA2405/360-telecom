# Telecom360 Agent Rules

## Product Intent

Build Telecom360 as a real full-stack platform, not a mock-only UI. Every user-facing workflow must eventually be backed by database models, API validation, role-based permissions, audit logging, and clear error handling.

## Roles

The system has four roles:

- `CUSTOMER`: registers, chooses company, reserves MSISDN, submits KYC, tracks activation, raises complaints/replacements.
- `SELLER`: verifies KYC, resolves failed activation cases, assists complaints and replacement workflows.
- `COMPANY`: monitors inventory, issued SIMs, failures, complaints, replacements, nodes, and analytics for its company.
- `ADMIN`: manages companies, sellers, plans, number series, SIM inventory, and system audit logs.

## Engineering Rules

- Backend validation is mandatory for every API.
- Never rely on frontend-only authorization.
- Use SQLAlchemy models and database constraints for core state.
- Use JWT claims plus server-side role checks for protected routes.
- Use Redis locks for temporary number reservation concurrency.
- Use WebSocket broadcasts for reservation disappearance, activation updates, and notifications.
- Preserve workflow state so failed activation resumes from the failed node, not from the beginning.
- Log sensitive business actions through the audit service.
- Keep phase changes small, tested, and compatible with Docker Compose.

## Data Rules

- Each SIM record must include `MSISDN`, `ICCID`, `IMSI`, `company_id`, and `status`.
- Number lists must be filtered by company/operator.
- A reserved number must become unavailable to other users immediately.
- ICCID/IMSI can be shown only after the customer has successfully reserved the MSISDN.
- Customer KYC is submitted once and reused during retry/resume flows.

## Frontend Rules

- Role-based home pages must reflect real role capabilities.
- Do not add fake-only workflows where the backend contract is missing; create the contract first or mark the UI as pending integration.
- Use React Flow for activation workflow visualization.
- Use Recharts for analytics.
- Keep dashboards operational and information-dense.

## Deployment Rules

- Docker Compose is the default local deployment path.
- `.env.example` must stay current when new environment variables are introduced.
- README startup instructions must be updated when services or ports change.

