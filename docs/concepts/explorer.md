# Explorer

The Explorer is a web application to present resources in Uptimely project.

Below is a screenshot from a feature lineage:

![Uptimely Core Demo](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-feature-lineage.png)

## How it works

A build creates a json file as an artifact, the the Explorer can present in browser.

The Explorer has web front end, that communicates with backend api. Both can be ran locally, but also deployed to remote server. Only requirement is access to the produces artifact file.

At the moment the Explorer does not allow backend interactions such as modifying the spec.

Techncally it would have all capabilities to do so.

## Explorer contents

Resource | Description
--- | ---
Logical layer | Profiles organized by category, features, dimensions, operators
Physical layer | Datasets and functions
Lineage | Feature level lineage, swimlane by profile
Compilation | Execution graph in topological visualization
Data preview | Materialize results from an engine run.
Engine run logs | Logs from the recent run
