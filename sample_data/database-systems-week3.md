# Database Systems — Week 3: Normalization

## Why normalize?

A poorly designed table repeats the same facts in many rows. Repetition causes three kinds of anomalies.
An update anomaly happens when one fact is stored in several rows and only some of them are changed.
An insertion anomaly happens when a fact cannot be recorded without also inventing unrelated data.
A deletion anomaly happens when deleting one row accidentally removes the only copy of another fact.
Normalization is the process of decomposing tables so that each fact is stored exactly once.

## Functional dependencies

A functional dependency X → Y means that the values of attributes X determine the values of attributes Y.
For example, in a table Enrolment(student_id, course_code, student_name), student_id → student_name.
A candidate key is a minimal set of attributes that functionally determines every other attribute.

## First normal form (1NF)

A table is in first normal form when every attribute holds a single atomic value and there are no repeating groups.
Storing a comma-separated list of phone numbers in one column violates 1NF.

## Second normal form (2NF)

A table is in second normal form when it is in 1NF and no non-key attribute depends on only part of a composite key.
In Enrolment(student_id, course_code, student_name, grade) the key is (student_id, course_code).
student_name depends only on student_id, which is a partial dependency, so the table is not in 2NF.
The fix is to move student_name into a separate Student(student_id, student_name) table.

## Third normal form (3NF)

A table is in third normal form when it is in 2NF and no non-key attribute depends on another non-key attribute.
Such a chain, key → A → B, is called a transitive dependency.
Example: Student(student_id, department_id, department_name) has student_id → department_id → department_name.

## Boyce–Codd normal form (BCNF)

BCNF is stricter than 3NF: for every non-trivial functional dependency X → Y, X must be a superkey.
Every BCNF table is in 3NF, but a 3NF table is not always in BCNF.

## Trade-offs

Highly normalized schemas need more joins, which can slow down read-heavy analytical queries.
Data warehouses therefore sometimes denormalize deliberately, for example with star schemas.
