# SQL and Uptimely

Uptimely provides a structured way to assemble scientific calculations and
tabular data into one workflow, without putting the calculations inside a
database. It combines Python functions with declared feature dependencies,
profile grains, and contracts for building datasets.

This is not a claim that SQL cannot do the same work. SQL and its ecosystem
can express modular transformations, track lineage, call Python functions,
and validate data. Uptimely brings a particular structure to these tasks,
especially when scientific calculations and tabular assembly need to work
together.

SQL serves a broad range of users and workloads. Uptimely focuses on data
scientists building analytical workflows, bringing specification,
calculation, validation, execution, and debugging into a unified experience.
This narrower focus lets it specialize in scientific Python calculations and
their dependencies, even when SQL-based tools can address the individual
needs.

## Where Uptimely can be a better fit

Uptimely is most compelling when a workflow combines several of these needs:

| Need | Benefit |
|---|---|
| Unified development workflow | Connect specification, calculation, validation, execution, and debugging for data scientists. |
| Scientific Python calculations | Use numerical libraries and domain-specific algorithms alongside tabular transformations. |
| Assembly across grains | Combine measurements, reference values, and calculated features at explicitly declared profile grains. |
| Feature lineage | Trace a feature to its declared inputs and calculations. |
| Selected execution | Run a calculation with its prerequisites. |
| Workflow debugging | Inspect execution statuses, logs, and previews to investigate results and failures. |
| Reusable function contracts | Test and debug Python calculations independently while their inputs, outputs, and assembly are described in the specification. |
| Control over execution | Keep calculation code outside a database's procedural environment and manage its Python dependencies separately. |

These benefits come with specification and runtime overhead. SQL is often the
better choice for data warehousing, large joins, filters, and aggregations.
Plain Python may be simpler for a small standalone calculation.

| | SQL | Uptimely |
|---|---|---|
| Main purpose | Query and transform data | Organize and run analytical workflows |
| What is declared | Queries, views, and other database objects | Profiles, features, calculations, and dependencies |
| Calculations | SQL expressions, database functions, or external code | Python functions with declared inputs and outputs |
| Assembly | Joins and other relational operations | Operators that build profile datasets |
| Lineage | Available through SQL tooling and surrounding frameworks | Derived from declared feature dependencies |

## Example: vibration spectrum

Suppose a data-center cooling pump produces a vibration burst of 4,096 samples at 1,024 samples
per second. An analyst wants the strongest vibration frequency between 10 and
200 Hz for each burst.

[Welch's method](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html)
estimates a power spectrum by dividing the signal into overlapping segments,
applying a window, calculating a spectrum for each segment, and averaging the
results. The numerical core for one burst can use SciPy:

```python
from scipy import signal

frequencies, power = signal.welch(
    vibration_samples,
    fs=1024,
    nperseg=1024,
    noverlap=512,
)

band = (frequencies >= 10) & (frequencies <= 200)
peak_hz = frequencies[band][power[band].argmax()]
```

In an Uptimely workflow, a Python function could apply this calculation to
each burst of samples. The resulting `peak_hz` feature could then be added to
a burst profile, where subsequent calculations could combine it with
operating conditions.

SQL is well suited to selecting and grouping the samples, but standard SQL
does not provide Welch's method as a common built-in. Some advanced algorithms
can be expressed in SQL, yet their expressions may become much more complex
than a call to a scientific library.

A database may offer Welch's method, a
general power spectral density function, or a Python UDF instead. Such
extensions can be useful, but a vendor-specific API is not portable standard
SQL. Keeping the implementation in ordinary Python can give a team more
control over its libraries, tests, and execution environment. It does not mean
that an SQL-based system cannot use the same algorithm.

## Structured dataset assembly

SQL can combine tables in many ways, and large queries without specified practices can become difficult
to understand. Views, common table expressions, and conventions can give SQL
workflows structure. Other frameworks can also enforce contracts and
dependencies.

Uptimely provides its own structure for applying tabular operations to
analytics. Each profile has a dataset that operators build up by adding
features. Calculations can be separated from the assembly that brings their
results into the profile.

This separation makes it easier to understand which function performs an
analytical calculation and how its result enters a profile. It does not
prevent a function from doing unrelated work or prove that its result is
correct.

## Developer workflow

Python supports scientific libraries, custom algorithms, and reusable
functions without requiring them to be expressed in SQL or installed as
database procedures. Developers can test calculations independently, set
breakpoints, and inspect intermediate values using familiar Python tools.

Uptimely reports invocation statuses, failures, and bounded previews. If an
invocation fails, remaining work is marked skipped. Run logs and previews
describe the latest run rather than a history of runs. Uptimely recommends
keeping analytical functions pure and leaving logging to the surrounding
workflow.

SQL platforms also provide debugging and diagnostics, though the available
tools vary by platform.

## Feature dependencies

SQL parsers and frameworks can trace dependencies across queries and views.
Uptimely instead makes feature dependencies part of the specification. This
can be useful when a graph mixes tabular assembly and opaque scientific
functions.

A SQL parser can trace the inputs passed to a UDF, but generally cannot infer
the UDF's internal behavior. Uptimely cannot infer arbitrary Python behavior
either. Its advantage is that the surrounding workflow has explicit contracts
even when the calculation is opaque. Lineage describes declared dependencies,
not hidden inputs or side effects.

The compiled plan identifies the work and prerequisites for selected
features. Uptimely can also run a selected calculation with its
prerequisites.

## Validation and deployment

Uptimely checks specification declarations and function contracts during compilation.
Runtime validation can additionally check declared inputs and dataframe
contracts, including keys and preservation requirements. It is opt-in and
does not establish that a formula is scientifically correct or that a
function is pure. Result tests and domain expertise remain necessary.

Keeping calculations as ordinary Python functions supports testing and
debugging outside the workflow. It also avoids requiring a database-specific
Python procedure. PostgreSQL and other open-source tools can run Python or
support external Python workflows too. Uptimely's distinction is the
surrounding specification and assembly contracts, not exclusive access to
Python.

The built-in engine currently supports Polars dataframes. Other dataframe
adapters and distributed execution are planned.
Arrow interchange is also planned, but interchange alone does not provide
native execution on another engine. Deploying the same function to a
SQL-driven platform would require a compatible runtime, dataframe interface,
and available Python dependencies. It is not currently guaranteed by
Uptimely.

## Using them together

Uptimely is not a replacement for SQL. SQL can retrieve and prepare data close
to the source, while Uptimely organizes scientific calculations and their
declared dependencies. Use SQL directly when a query is the clearest way to
express the work.

An operator's Python function can also use SQL through a dataframe library,
such as Polars, and return the resulting dataframe to Uptimely. This lets SQL
express a tabular transformation within the same analytical workflow.
