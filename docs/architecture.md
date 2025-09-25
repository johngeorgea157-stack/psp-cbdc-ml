sequenceDiagram
  participant User
  participant PSP
  participant DB
  participant Compliance

  User->>PSP: POST /transfer
  PSP->>DB: Validate + update balances
  PSP->>Compliance: Log transaction
  PSP-->>User: Success / Failure