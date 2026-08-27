# Praman_AI
AI-powered scanner that checks packaged-product labels against India's Legal Metrology (Packaged Commodities) Rules, 2011 — scan a label, get instant pass/fail with the exact rule violated.

# 🏷️ Label Compliance Scanner — SIH26034

An OCR-powered mobile/web tool that checks whether a packaged product's label 
complies with India's **Legal Metrology (Packaged Commodities) Rules, 2011** — 
built for Smart India Hackathon 2026.

## What it does
Scan or upload a photo of any packaged product label → the system extracts 
key declarations (MRP, net quantity, manufacturer details, date of 
manufacture, consumer-care contact) via OCR → validates each field against 
Legal Metrology rules → returns an instant **pass/fail report citing the 
exact rule violated**.

## Why it matters
Label compliance checks today are 100% manual — inspectors physically read 
and cross-check every label. This tool automates that check, giving both 
inspectors and everyday consumers a fast, reliable way to verify compliance 
without legal expertise.

**Problem Statement:** SIH26034 | **Ministry:** Consumer Affairs, Food & Public 
Distribution | **Track:** Software

## Tech Stack
OCR: Google Vision API / Tesseract · Backend: FastAPI · Rules Engine: Python 
· DB: PostgreSQL · Frontend: React

## Status
🚧 In development for SIH 2026
