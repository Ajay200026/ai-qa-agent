CONSTRAINTS = [
    "CREATE CONSTRAINT scenario_id IF NOT EXISTS FOR (s:Scenario) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT execution_id IF NOT EXISTS FOR (e:Execution) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT result_id IF NOT EXISTS FOR (r:Result) REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT app_section_id IF NOT EXISTS FOR (a:AppSection) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT field_id IF NOT EXISTS FOR (f:Field) REQUIRE f.id IS UNIQUE",
]

SECTIONS = [
    {"id": "login", "name": "Login", "app": "Salesforce"},
    {"id": "app_launcher", "name": "App Launcher", "app": "Salesforce"},
    {"id": "onboarding", "name": "Onboarding Application", "app": "Onboarding"},
    {"id": "customer_lifecycle", "name": "Customer Lifecycle", "app": "Onboarding"},
    {"id": "data_change", "name": "Data Change / New Request", "app": "Onboarding"},
]

FIELDS = [
    {"id": "module_selection", "name": "Module Selection", "section": "data_change"},
    {"id": "sales_office", "name": "Sales Office", "section": "data_change"},
    {"id": "customer_number", "name": "Customer Number", "section": "data_change"},
    {"id": "primary_group", "name": "Primary Group", "section": "data_change"},
]
