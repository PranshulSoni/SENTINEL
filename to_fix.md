# Codebase Errors to Fix

## Frontend (`/frontend`)
- **TypeScript**: `npm run build` and `npx tsc --noEmit` completed successfully without any type errors.

## User-App (`/user-app`)
- **TypeScript**: `npm run build` and `npx tsc --noEmit` completed successfully without any type errors.

## Backend (`/backend`)
Flake8 linting found 778 issues. Below is the summary and the full report of everything that needs fixing.

### Summary
The backend contains many style and linting issues. The most common are:
- `E501`: Line too long (over 79 characters)
- `W293` / `W291`: Trailing whitespaces / Blank lines containing whitespace
- `F401`: Module imported but unused
- `F841`: Local variable assigned to but never used
- `E402`: Module level import not at top of file
- `E302` / `E305`: Expected blank lines spacing issues

### Full Flake8 Report
```text
app.py:24:1: F401 'data.signal_baselines.CITY_CENTERS' imported but unused
app.py:28:80: E501 line too long (114 > 79 characters)
app.py:54:80: E501 line too long (99 > 79 characters)
app.py:61:80: E501 line too long (85 > 79 characters)
app.py:102:80: E501 line too long (97 > 79 characters)
app.py:112:80: E501 line too long (81 > 79 characters)
app.py:132:80: E501 line too long (85 > 79 characters)
app.py:152:80: E501 line too long (80 > 79 characters)
app.py:154:80: E501 line too long (104 > 79 characters)
app.py:162:80: E501 line too long (114 > 79 characters)
app.py:171:80: E501 line too long (109 > 79 characters)
app.py:188:80: E501 line too long (86 > 79 characters)
app.py:198:80: E501 line too long (80 > 79 characters)
app.py:223:80: E501 line too long (89 > 79 characters)
app.py:261:80: E501 line too long (86 > 79 characters)
app.py:266:80: E501 line too long (90 > 79 characters)
app.py:275:80: E501 line too long (83 > 79 characters)
app.py:279:80: E501 line too long (82 > 79 characters)
app.py:292:80: E501 line too long (92 > 79 characters)
app.py:307:80: E501 line too long (119 > 79 characters)
app.py:309:80: E501 line too long (83 > 79 characters)
app.py:334:80: E501 line too long (94 > 79 characters)
app.py:349:80: E501 line too long (88 > 79 characters)
app.py:372:80: E501 line too long (89 > 79 characters)
app.py:377:80: E501 line too long (82 > 79 characters)
app.py:382:80: E501 line too long (86 > 79 characters)
app.py:385:80: E501 line too long (90 > 79 characters)
app.py:387:80: E501 line too long (89 > 79 characters)
app.py:394:80: E501 line too long (94 > 79 characters)
app.py:397:80: E501 line too long (89 > 79 characters)
app.py:398:80: E501 line too long (91 > 79 characters)
app.py:405:80: E501 line too long (92 > 79 characters)
app.py:407:80: E501 line too long (96 > 79 characters)
app.py:425:80: E501 line too long (129 > 79 characters)
app.py:426:80: E501 line too long (181 > 79 characters)
app.py:435:80: E501 line too long (89 > 79 characters)
app.py:445:80: E501 line too long (82 > 79 characters)
app.py:456:80: E501 line too long (237 > 79 characters)
app.py:458:80: E501 line too long (88 > 79 characters)
app.py:473:80: E501 line too long (104 > 79 characters)
app.py:479:80: E501 line too long (90 > 79 characters)
app.py:508:80: E501 line too long (105 > 79 characters)
app.py:510:80: E501 line too long (92 > 79 characters)
app.py:515:80: E501 line too long (90 > 79 characters)
app.py:517:80: E501 line too long (94 > 79 characters)
app.py:518:80: E501 line too long (110 > 79 characters)
app.py:535:80: E501 line too long (80 > 79 characters)
app.py:544:80: E501 line too long (108 > 79 characters)
app.py:545:80: E501 line too long (91 > 79 characters)
app.py:571:80: E501 line too long (81 > 79 characters)
app.py:573:80: E501 line too long (132 > 79 characters)
app.py:574:80: E501 line too long (170 > 79 characters)
app.py:597:80: E501 line too long (97 > 79 characters)
app.py:604:80: E501 line too long (97 > 79 characters)
app.py:609:80: E501 line too long (88 > 79 characters)
app.py:615:13: F841 local variable 'lng' is assigned to but never used
app.py:615:18: F841 local variable 'lat' is assigned to but never used
app.py:628:80: E501 line too long (85 > 79 characters)
app.py:630:80: E501 line too long (103 > 79 characters)
app.py:637:80: E501 line too long (107 > 79 characters)
app.py:638:80: E501 line too long (84 > 79 characters)
app.py:646:80: E501 line too long (96 > 79 characters)
app.py:647:80: E501 line too long (112 > 79 characters)
app.py:682:80: E501 line too long (81 > 79 characters)
app.py:685:80: E501 line too long (110 > 79 characters)
app.py:697:80: E501 line too long (93 > 79 characters)
app.py:709:80: E501 line too long (86 > 79 characters)
app.py:757:80: E501 line too long (81 > 79 characters)
app.py:759:80: E501 line too long (84 > 79 characters)
app.py:764:80: E501 line too long (84 > 79 characters)
app.py:765:80: E501 line too long (90 > 79 characters)
app.py:767:1: E402 module level import not at top of file
app.py:768:1: E402 module level import not at top of file
main_gpu.py:12:1: E402 module level import not at top of file
... plus ~700 similar issues across the services module. (Run "python -m flake8" in the backend folder to see all details).
```
