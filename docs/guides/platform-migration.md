# Platform migrations

Data and analytics platforms cost millions of dollars annually for big companies.

Major platforms such as SnowPark, Spark, BigQuery and others provide implementation design primarily for their platform. While you theoretically can use the code elsewhere, in reality the calculations can not be transferred without massive migration burden.

Everybody knows how that go: Long migration project without guarantees that the results will be the same.

While it's impossible to abstract everything in data analytics, Uptimely Core is on the way to make migrations less painful and keep doors open for platform tendering.

## Semantical layer

The spec describes in open json format what calculations you need. Even though the calculation code needs to still decide which implementation to use. The difference is that implementation is generic, while computational logic is encoded to operators in the semantical layer.

## Split to small items

Uptimely framework forces to split implementation the analytics in atomic units that are easy to replace.

It easier to replace something like this:

```py

def read(connection):
    return data

def filters(data, conditions: list[str]):
    return data

def aggregate(data, method: str, cols: list)
    return data

def overheat_inference(data, cols: list[str], optimizer: str)
    return data
```

Instead of this:

```py
def prepare_do_many_loops_and_infer_something():

    # 1000 lines of code with nested functions

    return {"hello": "world", "retults:": df_67}, [logs, 42]
```

## Know what is calculated

Automated feature level lineage and documentation guarantees that you are comparing apples to apples, and you know if the results are correct.

## Automated tests

Uptimely enforces automated tests by simple function input and output data comparison. This remains the same regardless of the chosen platform.
