# Organizational Model

## 1. Target Structure
The target model is multi-company and multi-site by design:

- Holding
  - Company
    - Site / Work Location
      - Department
        - Unit
          - Employee

## 2. Constraints
- More than one company can be defined.
- Each company may have multiple sites or operational locations.
- Each site may contain several departments or units.
- The structure is not locked to only two locations.
- Employee transfers between units are trackable.
- The direct manager of each employee can be assigned explicitly.
- Org changes remain auditable over time.

## 3. Current State
The present ORM includes `Company`, `Department`, and `EmployeeProfile` with a manager relationship. This is sufficient as a foundation but still needs a formalized organizational hierarchy and future expansion for site / unit / contract-level data.

## 4. Future Requirements
- Site / WorkLocation table with company ownership and regional metadata
- OrganizationalUnit table for business-unit and department decomposition
- Responsible manager history for each employee transfer
- EmploymentContract relationship for contractual working patterns and leave policy subscriptions
- Department lineage and effective-dates metadata for organizational history
