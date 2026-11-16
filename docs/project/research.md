# Data science research

## Deep learning projects unit tests

The paper: https://arxiv.org/abs/2402.16546

68% of the researched 9,129 open source deep learning GitHub repos had not unit tests. And 56%
of the tested projects have less than 30% of the files associated with tests

Only 5% of projects have coverage of over 90%.

> In final examination 363 projects come from various sources, including ready-to-use frameworks, academic research works, and industry projects from large tech companies(e.g., Google, IBM, LinkedIn, and Uber).

The following implies that the results have very little validation:

> More than 70% of the unit tests test the Layer and Util unit in DL projects. Activation Function, Optimizer, and Loss Function are the least tested.

> Nevertheless, Islam et al. [39] found that 31 out of 50 randomly selected crashed bugs in DL projects either had no messages or the fixes were unrelated to the returned messages

> For example, the user tried to build a classifier to predict the match results [4], but the model always outputs 0% Loss and 100% Accuracy with no error messages.
