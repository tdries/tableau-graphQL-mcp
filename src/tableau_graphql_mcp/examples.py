"""Curated Tableau lineage question -> GraphQL library, and a schema cheat-sheet.

Embedded so the model can ground its GraphQL in correct, working query shapes.
Exposed to clients through the ``lineage_examples`` tool and referenced by
``graphql_query``'s description. All examples use generic, Superstore-style names.
"""

from __future__ import annotations

SCHEMA_CHEATSHEET = """TABLEAU METADATA API : GRAPHQL CHEAT SHEET (read-only)

Filters are EXACT and case-sensitive. Use `name` for one value or `nameWithin:[...]`
to OR-match several (the only multi-match; there is no substring or regex). Every list
field has a `<name>Connection` variant with `first`/`offset`/`after` + `pageInfo`
(max page 1000). Keep a single query under ~20,000 nodes: narrow filters, page the
outer connection, and split deep nesting into a second `luidWithin`/`idWithin` query.

QUERY ENTRY POINTS (each also *Connection):
  workbooks · sheets · dashboards · views · publishedDatasources · embeddedDatasources
  · datasources · fields · columnFields · calculatedFields · parameters · columns
  · databaseTables · customSQLTables · tables · databases · databaseServers
  · virtualConnections · flows · lenses · metrics · tableauUsers · tags
  · dataQualityWarnings · dataQualityCertifications

KEY TYPES & LINEAGE FIELDS (lineage is uniform: upstream<Type> / downstream<Type>):
  Workbook: name luid projectName owner{username} sheets dashboards
            embeddedDatasources{name fields} upstreamTables upstreamDatabases upstreamDatasources
  Sheet:    name workbook{name} worksheetFields sheetFieldInstances containedInDashboards
            upstreamColumns upstreamTables upstreamFields
  Dashboard:name workbook{name} sheets upstreamDatasources upstreamColumns upstreamFields
  Column:   name remoteType isNullable table{...} referencedByFields{name}
            upstream/downstream: Columns Fields Tables Sheets Dashboards Workbooks Datasources Owners
  Field (interface -> ColumnField, CalculatedField, GroupField, BinField, SetField, HierarchyField, CombinedField):
            name __typename datasource{...} sheets
            ...on ColumnField{ columns{name table{...}} }   ...on CalculatedField{ formula fields{name} }
  DatabaseTable: name schema fullName database{name connectionType} columns{name}
            downstream: Workbooks Sheets Dashboards Owners   upstream: Tables Databases Datasources
  CustomSQLTable: name query columns database{...}
  PublishedDatasource: name luid isCertified hasExtracts owner{username}
            upstreamTables downstreamWorkbooks
  EmbeddedDatasource: name workbook{name} fields (the reliable field -> workbook bridge)
  Database/DatabaseServer: name connectionType tables
  TableauUser: username name email

CROSS-CUTTING NOTES:
- `datasource{ __typename ...on EmbeddedDatasource{ workbook{name} } ...on PublishedDatasource{name} }`
  is how you go field -> owning workbook (an embedded datasource belongs to one workbook).
- `downstream*` fields (downstreamWorkbooks/Owners/Sheets, external tables/columns) need the
  Data Management add-on (Tableau Catalog). When empty, resolve via core lineage instead:
  column.referencedByFields -> field.sheets -> sheet.workbook, and field.datasource -> workbook.
- On Tableau Server the Metadata API must be enabled; on Tableau Cloud it is always on.
- ids: `id` (opaque Metadata id) is not `luid` (REST/Server GUID) is not `vizportalUrlId` (URL slug).
"""

# Each example: category, question, graphql, variables (JSON string), notes.
# Names are generic Superstore-style placeholders, not real content.
EXAMPLES: list[dict[str, str]] = [
    # a. Where-used / impact analysis ---------------------------------------
    {
        "category": "impact",
        "question": "If I rename or drop the database column SALES, which Tableau fields, sheets, dashboards and workbooks break?",
        "graphql": """query ColumnImpact($name: String!) {
  columns(filter: { name: $name }) {
    name
    table {
      __typename
      ... on DatabaseTable { name schema fullName database { name connectionType } }
      ... on CustomSQLTable { name database { name } }
    }
    referencedByFields {
      name
      __typename
      datasource {
        __typename
        ... on EmbeddedDatasource { name workbook { name projectName owner { username } } }
        ... on PublishedDatasource { name }
      }
      sheets { name workbook { name } }
    }
    downstreamWorkbooks { name projectName owner { username } }
    downstreamSheets { name }
    downstreamDashboards { name }
    downstreamOwners { username }
  }
}""",
        "variables": '{ "name": "SALES" }',
        "notes": "referencedByFields + sheets are core lineage and always work; downstream* need Catalog. Exact, case-sensitive filter.",
    },
    {
        "category": "impact",
        "question": "Which workbooks and worksheets use the field named 'Profit Ratio' (column or calc field)?",
        "graphql": """query FieldWhereUsed($name: String!) {
  fields(filter: { name: $name }) {
    name
    __typename
    datasource {
      __typename
      ... on EmbeddedDatasource { name workbook { name projectName owner { username } } }
      ... on PublishedDatasource { name }
    }
    sheets { name workbook { name } }
    ... on ColumnField { columns { name table { __typename ... on DatabaseTable { name schema } } } }
    ... on CalculatedField { formula }
  }
}""",
        "variables": '{ "name": "Profit Ratio" }',
        "notes": "`fields` returns every Field subtype; empty `sheets` means the field lives only in the datasource, not on a viz.",
    },
    {
        "category": "impact",
        "question": "What is the full downstream impact of the database table DIM_CUSTOMER?",
        "graphql": """query TableImpact($name: String!) {
  databaseTables(filter: { name: $name }) {
    name
    schema
    fullName
    database { name connectionType }
    downstreamWorkbooks { name projectName owner { username } }
    downstreamSheets { name }
    downstreamDashboards { name }
    downstreamOwners { username }
    columns { name referencedByFields { name } }
  }
}""",
        "variables": '{ "name": "DIM_CUSTOMER" }',
        "notes": "downstream* needs Catalog; if empty, fall back to columns{ referencedByFields{ sheets{ workbook{name} } } }. Table names repeat across databases.",
    },
    {
        "category": "impact",
        "question": "Blast radius of several columns at once (migration touching many columns).",
        "graphql": """query MultiColumnImpact($names: [String]) {
  columns(filter: { nameWithin: $names }) {
    name
    table { __typename ... on DatabaseTable { name schema } }
    referencedByFields {
      name
      sheets { name workbook { name } }
      datasource { __typename ... on EmbeddedDatasource { workbook { name } } ... on PublishedDatasource { name } }
    }
  }
}""",
        "variables": '{ "names": ["SALES", "PROFIT", "DISCOUNT"] }',
        "notes": "nameWithin matches any exact name in the list in one call. Keep total nodes under ~20000; page if the set is large.",
    },
    # b. Provenance / what-feeds --------------------------------------------
    {
        "category": "provenance",
        "question": "What databases and tables does the workbook 'Sales Overview' depend on?",
        "graphql": """query WorkbookProvenance($name: String!) {
  workbooks(filter: { name: $name }) {
    name
    projectName
    owner { username }
    upstreamDatabases { name connectionType }
    upstreamTables { name schema fullName database { name } }
    embeddedDatasources { name upstreamTables { name } fields { name __typename } }
  }
}""",
        "variables": '{ "name": "Sales Overview" }',
        "notes": "upstreamTables/Databases are Catalog-backed but usually populated for live DB connections; embeddedDatasources.fields is core.",
    },
    {
        "category": "provenance",
        "question": "Give me the field-to-source-column map for a workbook (which physical column backs each field).",
        "graphql": """query WorkbookFieldColumns($name: String!) {
  workbooks(filter: { name: $name }) {
    name
    embeddedDatasources {
      name
      fields {
        name
        __typename
        ... on ColumnField { columns { name table { __typename ... on DatabaseTable { name schema } ... on CustomSQLTable { name } } } }
        ... on CalculatedField { formula }
      }
    }
  }
}""",
        "variables": '{ "name": "Sales Overview" }',
        "notes": "Pure core lineage: works without Catalog. ColumnField.columns gives the backing DB column(s); CalculatedField has a formula, no columns.",
    },
    {
        "category": "provenance",
        "question": "What data does the dashboard 'Executive Summary' pull from (sheets, datasources, tables, columns)?",
        "graphql": """query DashboardProvenance($name: String!) {
  dashboards(filter: { name: $name }) {
    name
    workbook { name projectName }
    sheets { name }
    upstreamDatasources { name }
    upstreamTables { name schema database { name } }
    upstreamColumns { name table { __typename ... on DatabaseTable { name } } }
    upstreamFields { name __typename }
  }
}""",
        "variables": '{ "name": "Executive Summary" }',
        "notes": "Dashboard names are not unique across workbooks, so results may span several. upstream* need Catalog.",
    },
    {
        "category": "provenance",
        "question": "Which exact columns and tables feed one specific worksheet?",
        "graphql": """query SheetProvenance($name: String!) {
  sheets(filter: { name: $name }) {
    name
    workbook { name }
    worksheetFields { name __typename }
    upstreamColumns { name table { __typename ... on DatabaseTable { name schema } } }
    upstreamTables { name schema }
    upstreamDatasources { name }
  }
}""",
        "variables": '{ "name": "Sales by Region" }',
        "notes": "worksheetFields = fields placed on the sheet (core); upstreamColumns needs Catalog. Sheet names repeat across workbooks.",
    },
    # c. Calculated-field dependencies --------------------------------------
    {
        "category": "calc",
        "question": "What does the calculated field 'Profit Ratio' reference?",
        "graphql": """query CalcReferences($name: String!) {
  calculatedFields(filter: { name: $name }) {
    name
    formula
    datasource {
      __typename
      ... on EmbeddedDatasource { name workbook { name } }
      ... on PublishedDatasource { name }
    }
    fields {
      name
      __typename
      ... on CalculatedField { formula }
      ... on ColumnField { columns { name table { __typename ... on DatabaseTable { name } } } }
    }
  }
}""",
        "variables": '{ "name": "Profit Ratio" }',
        "notes": "`fields` = the calc's DIRECT references only; a calc referencing another calc needs a second query on that name (recurse).",
    },
    {
        "category": "calc",
        "question": "Which calculated fields reference the column SALES (reverse dependency)?",
        "graphql": """query ColumnConsumers($name: String!) {
  columns(filter: { name: $name }) {
    name
    table { __typename ... on DatabaseTable { name schema } }
    referencedByFields {
      name
      __typename
      ... on CalculatedField { formula }
      datasource { __typename ... on EmbeddedDatasource { workbook { name } } ... on PublishedDatasource { name } }
    }
  }
}""",
        "variables": '{ "name": "SALES" }',
        "notes": "referencedByFields is ONE hop (direct consumers). For the full transitive downstream chain (calc-of-a-calc), use the impact_analysis tool, which walks it for you.",
    },
    {
        "category": "calc",
        "question": "List every calculated field in a workbook with its formula and direct references (calc audit).",
        "graphql": """query WorkbookCalcs($name: String!) {
  workbooks(filter: { name: $name }) {
    name
    embeddedDatasources {
      name
      fields {
        __typename
        ... on CalculatedField { name formula fields { name __typename } }
      }
    }
  }
}""",
        "variables": '{ "name": "Sales Overview" }',
        "notes": "Only CalculatedField nodes carry `formula`. Core lineage.",
    },
    # d. Published datasource lineage ---------------------------------------
    {
        "category": "datasource",
        "question": "What physical tables and databases feed the published datasource 'Superstore'?",
        "graphql": """query PublishedDatasourceUpstream($name: String!) {
  publishedDatasources(filter: { name: $name }) {
    name
    luid
    hasExtracts
    owner { username }
    upstreamDatabases { name connectionType }
    upstreamTables { name schema fullName database { name } }
    fields { name __typename }
  }
}""",
        "variables": '{ "name": "Superstore" }',
        "notes": "Datasource names are not globally unique; add a luid filter to pin one. upstreamTables need Catalog.",
    },
    {
        "category": "datasource",
        "question": "Which workbooks depend on the published datasource 'Superstore' (change impact)?",
        "graphql": """query PublishedDatasourceDownstream($name: String!) {
  publishedDatasources(filter: { name: $name }) {
    name
    luid
    downstreamWorkbooks { name projectName owner { username } }
    downstreamSheets { name }
    downstreamDashboards { name }
  }
}""",
        "variables": '{ "name": "Superstore" }',
        "notes": "downstreamWorkbooks is Catalog-backed and can be empty without Data Management, then reverse via each workbook's upstreamDatasources.",
    },
    {
        "category": "datasource",
        "question": "Inventory all published datasources in a project with certification and extract status.",
        "graphql": """query DatasourceInventory($project: String, $first: Int!, $after: String) {
  publishedDatasourcesConnection(filter: { projectName: $project }, first: $first, after: $after) {
    nodes { name luid projectName isCertified hasExtracts owner { username } }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}""",
        "variables": '{ "project": "Analytics", "first": 100, "after": null }',
        "notes": "Use the *Connection variant with first/after; loop on pageInfo.hasNextPage. Omit the filter to list site-wide (mind the node limit).",
    },
    # e. Discovery / search -------------------------------------------------
    {
        "category": "search",
        "question": "Look up several names at once across content types (which of these exist and as what)?",
        "graphql": """query FindMany($names: [String]) {
  workbooks(filter: { nameWithin: $names }) { name projectName }
  publishedDatasources(filter: { nameWithin: $names }) { name projectName }
  databaseTables(filter: { nameWithin: $names }) { name schema database { name } }
  fields(filter: { nameWithin: $names }) { name __typename }
}""",
        "variables": '{ "names": ["Superstore", "SALES", "Sales Overview"] }',
        "notes": "nameWithin is exact-match OR across the list. One round-trip classifies each name against every asset type.",
    },
    {
        "category": "search",
        "question": "Substring / 'contains' search for a workbook when I only know part of the name.",
        "graphql": """query AllWorkbooks($first: Int!, $after: String) {
  workbooksConnection(first: $first, after: $after) {
    nodes { name projectName owner { username } updatedAt }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}""",
        "variables": '{ "first": 100, "after": null }',
        "notes": "No server-side substring/regex filter: page with first/after and match names client-side. totalCount tells you how many pages.",
    },
    {
        "category": "search",
        "question": "Global lookup: does 'Region' exist as a workbook, field, column, or table?",
        "graphql": """query GlobalSearch($name: String!) {
  workbooks(filter: { name: $name }) { name projectName }
  fields(filter: { name: $name }) { name __typename datasource { __typename ... on EmbeddedDatasource { workbook { name } } } }
  columns(filter: { name: $name }) { name table { __typename ... on DatabaseTable { name schema } } }
  databaseTables(filter: { name: $name }) { name schema database { name } }
}""",
        "variables": '{ "name": "Region" }',
        "notes": "Exact-match on each entry point in one query classifies the term across the graph.",
    },
    # f. Database / table inventory -----------------------------------------
    {
        "category": "inventory",
        "question": "List all databases the site knows about, with connection type.",
        "graphql": """query DatabaseInventory($first: Int!, $after: String) {
  databasesConnection(first: $first, after: $after) {
    nodes { name connectionType isCertified }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}""",
        "variables": '{ "first": 100, "after": null }',
        "notes": "Connection variant + paging; the plain databases{} field can exceed the node limit on large sites. Needs Catalog.",
    },
    {
        "category": "inventory",
        "question": "Column-level detail for one table: data types and nullability.",
        "graphql": """query TableColumns($name: String!) {
  databaseTables(filter: { name: $name }) {
    name schema fullName
    database { name connectionType }
    columns { name remoteType isNullable }
  }
}""",
        "variables": '{ "name": "FACT_SALES" }',
        "notes": "remoteType is the source system's type string. Table names collide across schemas/databases: add a database filter to disambiguate.",
    },
    {
        "category": "inventory",
        "question": "What Custom SQL is a workbook running against the database?",
        "graphql": """query WorkbookCustomSql($name: String!) {
  workbooks(filter: { name: $name }) {
    name
    embeddedDatasources {
      name
      fields {
        ... on ColumnField {
          name
          columns { table { __typename ... on CustomSQLTable { name query database { name } } } }
        }
      }
    }
  }
}""",
        "variables": '{ "name": "Sales Overview" }',
        "notes": "Custom SQL never appears in upstreamTables; reach it through Column.table resolving to CustomSQLTable, whose `query` holds the raw SQL.",
    },
    # g. Orphans & governance -----------------------------------------------
    {
        "category": "governance",
        "question": "Which columns of a table are unused (referenced by no field / no downstream content)?",
        "graphql": """query UnusedColumns($name: String!) {
  databaseTables(filter: { name: $name }) {
    name
    columns { name referencedByFields { name } downstreamFields { name } }
  }
}""",
        "variables": '{ "name": "DIM_REGION" }',
        "notes": "No 'is empty' filter: pull all columns and keep those where referencedByFields AND downstreamFields are empty. downstreamFields needs Catalog.",
    },
    {
        "category": "governance",
        "question": "Show all active data-quality warnings on the site (deprecated / stale / sensitive / warning).",
        "graphql": """query DataQualityWarnings($first: Int!, $after: String) {
  dataQualityWarningsConnection(first: $first, after: $after) {
    nodes {
      luid warningType message isActive isSevere createdAt
      author { username }
      asset {
        __typename
        ... on DatabaseTable { name schema }
        ... on PublishedDatasource { name }
        ... on Column { name }
        ... on Database { name }
      }
    }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}""",
        "variables": '{ "first": 100, "after": null }',
        "notes": "Requires Data Management (Catalog). Segment by warningType (WARNING / DEPRECATED / STALE / SENSITIVE_DATA) client-side.",
    },
    {
        "category": "governance",
        "question": "Certification status of every published datasource in a project.",
        "graphql": """query CertificationStatus($project: String, $first: Int!, $after: String) {
  publishedDatasourcesConnection(filter: { projectName: $project }, first: $first, after: $after) {
    nodes { name isCertified certificationNote certifier { username } owner { username } }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}""",
        "variables": '{ "project": "Analytics", "first": 100, "after": null }',
        "notes": "isCertified/certifier/certificationNote come from the Certifiable interface (also on Database, DatabaseTable, Column, Flow).",
    },
    # h. Ownership & stewardship --------------------------------------------
    {
        "category": "ownership",
        "question": "Who owns this workbook and datasource?",
        "graphql": """query OwnerLookup($name: String!) {
  workbooks(filter: { name: $name }) { name projectName owner { username name email } }
  publishedDatasources(filter: { name: $name }) { name owner { username name email } }
}""",
        "variables": '{ "name": "Sales Overview" }',
        "notes": "owner is a TableauUser (username/name/email; email may be null depending on site settings).",
    },
    {
        "category": "ownership",
        "question": "Who should I notify before changing table DIM_CUSTOMER (all downstream owners)?",
        "graphql": """query WhoToNotify($name: String!) {
  databaseTables(filter: { name: $name }) {
    name
    downstreamOwners { username name email }
    downstreamWorkbooks { name owner { username } }
  }
}""",
        "variables": '{ "name": "DIM_CUSTOMER" }',
        "notes": "downstreamOwners is the de-duplicated owner set across all downstream content, your notification list. Needs Catalog; else derive via columns{ referencedByFields{ ... workbook{ owner } } }.",
    },
    {
        "category": "ownership",
        "question": "Who is the steward/certifier of the table and datasource (governance contact)?",
        "graphql": """query Stewardship($name: String!) {
  databaseTables(filter: { name: $name }) {
    name isCertified certificationNote
    certifier { username name }
    downstreamOwners { username }
  }
  publishedDatasources(filter: { name: $name }) {
    name isCertified certificationNote
    certifier { username name }
    owner { username }
  }
}""",
        "variables": '{ "name": "Superstore" }',
        "notes": "certifier is who certified the asset (a steward signal); downstreamOwners lists owners of everything built on the table.",
    },
]

CATEGORIES = {
    "impact": "Where-used / impact analysis (blast radius of a column, field, table, datasource)",
    "provenance": "Provenance / what-feeds (tables, columns, datasources behind a workbook, dashboard or sheet)",
    "calc": "Calculated-field dependencies (what a calc references; what references a column)",
    "datasource": "Published datasource lineage (upstream tables, downstream workbooks, inventory)",
    "search": "Discovery / search (find content by exact name across asset types)",
    "inventory": "Database / table / column inventory (the physical layer, incl. Custom SQL)",
    "governance": "Orphans & governance (unused columns, data-quality warnings, certification)",
    "ownership": "Ownership & stewardship (owners, certifiers, who to notify)",
}
