# Features to add to the code

## Sets from ABAQUS to FEniCS
- it is not clear how FEniCS makes sets from ABAQUS input files, so first we need to find out the procedure for adding sets into FEniCS
- Then the sets can be easily extracted from ABAQUS and rewritten in XML files

## Handling of errors
- Some error handling is implemented but are very basic
- In order to add better error handling capabilities, I need to learn more about how to work with errors and raise exceptions in Python
- Some of the errors are not added to the code at all (maybe the best approach is to wait to see those errors and then implement them in the code)
