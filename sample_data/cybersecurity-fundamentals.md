# Cybersecurity Fundamentals — Week 1

## The CIA triad

Confidentiality means information is disclosed only to authorised parties; encryption and access control support it.
Integrity means information is not altered without detection; hashes and digital signatures support it.
Availability means systems and data are accessible when needed; redundancy and DDoS protection support it.

## Authentication factors

Authentication verifies identity using something you know (a password), something you have (a hardware key or phone)
or something you are (a fingerprint). Multi-factor authentication combines at least two different factor types.

## Hashing passwords

Passwords should never be stored in plain text. Systems store a salted hash produced by a slow algorithm such as
bcrypt, scrypt or Argon2. A salt is a random value stored with each hash so that identical passwords produce different
hashes, which defeats precomputed rainbow tables.

## Common attacks

Phishing tricks users into revealing credentials through deceptive messages or websites.
SQL injection occurs when untrusted input is concatenated into a SQL query; parameterised queries prevent it.
Cross-site scripting (XSS) injects malicious scripts into pages viewed by other users; output encoding mitigates it.

## Principle of least privilege

Every user and process should receive only the permissions required for its task, which limits the damage
caused by mistakes or compromised accounts.
