# The problem that Uptimely Core solves

Uptimely Core aims to reduce the specification and development process for massive scale numerical calculations with complex dependencies for industrial needs from weeks to minutes.

## Example story

The following story is imagined. However, it is inspired and compiled by discussions from developers and business managers across the industry. The example is not exceptional, and those ~60 steps could be easily multiplied in many occassions.

Data scientist in a chemical production company is asked to develop a simple new calculation for a production line to monitor its performance.

Let's say the required calculation is simply picking lower value among two measurements in the process telemetry data:

```sql
min(flow_rate_1, flow_rate_2)
```

## The development process

The workflow for data scientist might look something like this:

1. Go to ticketing tool
2. Find the right ticket
3. Check description: "Apply `min(flow_rate_1, flow_rate_2)` for production line x"
4. Browse documentation wiki if existing analytics framework would allow such function
5. Also go through each repository to double check if documentation was up to date
4. Result: Documentation was outdated
6. Ask in company chat if somebody has deployed anything similar
7. Also check the database catalog if there are similar calculations running
9. There is similar calculation running but it is not compatible with this type of production line
10. Fire the deployment pipeline. But wait! There is a rivaling deployment running.
11. Check for conflicts in the code.
12. Conflict. Resolve in code editor.
13. Ask in chat if somebody has other stuff coming soon
14. Deploy
15. Deployment error. An automatically updated code package is not compatible with others.
16. Fix and deploy. Wait for an hour to pass all safeguards.
17. Deployment passes.
18. Wait for Python environment setup and execution.
19. Error: There was a syntax error that was captured only in the production environment
20. Realize a new version needs to be deployed
21. The person responsible of existing repositories is on vacation, due to lack of permission, you need to create a new repo
22. You try to find the project template repository
23. There is no simple way to parametrize the calculation, so you hard code `min(flow_rate_1, flow_rate_2)` to the code
24. Change and deploy. Wait for an hour to finish.
25. Wait another 30 minutes for results due to runtime environment setup from zero and massive data read.
26. Finally results are ready. Check results manually.
27. Run 25 queries to find out what data was persisted to database
28. Results are not visible, not sure why
29. Check that we have data for the production line
30. Find the id of the production line by a complex SQL query
31. Read wiki about how to add a new production line to database
32. The page was updated 3 years ago, the process does not work
33. Try various things and make it work
34. You verify from the project manager by email when the results are needed
35. Suddenly there is a sprawling email thread of 13 managers, engineers and sales people about the exact definition
36. Main stakeholder asks in the middle of thread WHEN IS IT READY
36. The definition was multiple KPIs over various time periods
37. Go back to code
38. A week passes due to unclarity of new specifications
39. Works locally
40. It is already afternoon and there is nobody to accept code changes
41. Next day deploy to cloud
42. It kind of works, but there is a dependent calculation that is not in sync
43. Fix it
44. The executor runs out of memory
45. Fortunately you have a massive big data parallel processing cluster as well
46. Accommodate the code
47. But it runs out of memory because underlying data is not partitioned
48. Change to a bigger computes instance
49. Finally works in a notebook! Deploy :)
50. Hmm, there is no deployment pipeline to handle notebooks
51. Just pick the most enormousest virtual server and deploy
52. Passes. Executes. Results are there.
53. Works, but the results are duplicated.
54. Whatever, the results are there
55. Update wiki page for the calculation
56. Also update the pull request notes
57. And once more in the ticket...
58. Explain the same also to everybody in the email
59. Answer follow-up questions in the email one more time to realize nobody reads any of the documentation
59. This was only devevelopment environment. Repeat the steps for to QA and production.

## Why the problem exists?

It is not the lack of technical tools or data science expertise. There are sophisticated components for to run massive workflows in data platform, dataframes, machine learning libraries etc tooling. The real problem is that they are focused on technogolgy and execution instead of managing the big picture.

Compare it to building a house. You have hammer, nails and a pile of wood. But no guidelines to build. Somebody thinks the house should be a hole in the ground, another insist for tree hut. Nobody knows how the house even should look like, but everybody has opinion.

How do you scale to city level from this starting point?

## Missing governance layer for analytics

Modern data platforms such as Snowflake, Databricks and BigQuery allow data analytics in any scale and complexity.

While it is amazing techical achievement, it also leads to a governance chaos. The intention of those platforms is mainly to provide technical execution power and engineering tools.

Especially with AI coding assistant, creating a single calculation is not a bottleneck anymore. Today's issue is managing all of them.

The data science ecosysytem is missing the layer to manage and structure the analytical calculation on those platforms and frameworks in an easy way. Or even making them invisible.

What if somebody could have just gone to a mobile app, write the minimal analytical expression to an input box and click "Deploy"?

## The specification process

Before the development process has started, there has been dozens of meetings to define project requirements and what needs to be achieved and how is it implemented. Who does what and when.

And the only question that anybody is really interested about: **When is it ready?**

The developer knows there is no realistic answer due to the described process. But to please everyone they give an estimation.

Uptimely Core provides a highly structured specification and process to bypass all intermediate steps. The person who needs the analytics can directly submit a draft for a data scientist to review and deploy.

## From basics to state of the art

When are experts supposed to create real science having such workflows?

Solving the above process would harness smart people to focus on real industrial intelligence where they can really shine. It removes a massive communication and information overhead between multiple developers and stakeholders.

Uptimely Core was born as a result of frustration to missing tooling to build analytical pipelines that are easy to organize, deploy and understand.

Uptimely has ambition to build reusable modular components for advanced industrial use cases such as production optimization with quantum computing and generic industrial multi-sensor anomaly detection. Before that, it was important to build robust and scalable foundations.
