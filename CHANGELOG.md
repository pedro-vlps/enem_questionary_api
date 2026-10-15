# Changelog

## v0.5.0 - 2026-10-15

- Add environment-controlled question generation with database retrieval as the default.
- Return question sources and preserve support materials when reusing stored questions.
- Initialize OpenAI clients only when generation is requested.
- Add regression tests for generation controls and stored question retrieval.

## v0.4.0

- Manual questions route added
- Support materials routes added
- Questions generation using support material routes added
- Database update added

## v0.3.0

- Manual question creation added 

## v0.2.0

- Implemented Charts, texts and images implementation to the questions generation
- Added s3 to save images
- Improvements to the prompt for questions generation

## v0.1.0

- Login, Register and Forgot Password route created
- JWT token setup created
- Adjustments on compose file to save database between down's and up's
- JWT and Fernet utils added
- Email utils added
- Created tables to manage cupons usage
- Basic questions generation routes created

## v0.0.1

- Created project setup

