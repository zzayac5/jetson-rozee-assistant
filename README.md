# Rozee  
## A Context-Aware Personal Operations Assistant

Rozee is a productivity system designed to turn large unstructured brain dumps into prioritized execution plans.

Unlike traditional task managers that rely primarily on due dates, Rozee evaluates tasks using multiple contextual variables such as urgency, importance, duration, dependencies, schedule availability, and cognitive load.

The goal is to help answer a more meaningful question:

**What should I actually work on next?**

---

## Project Overview

Rozee is currently being developed as part of the `jetson-ui` project. The system is designed to run locally and eventually integrate with voice interfaces, scheduling data, and AI-assisted task parsing.

The first stage of Rozee focuses on solving a very common problem:

People have a large number of things they need to do but struggle to determine what should be done first.

Rozee aims to reduce that friction.

---

## Core Concept

Rozee begins with a **brain dump workflow**.

Users enter everything they need to do without worrying about structure or prioritization.

Example input:

Finish project proposal  
Call insurance company  
Schedule dentist appointment  
Prepare slides for Monday briefing  
Research GPU hardware for AI server  

Rozee then converts this raw input into structured task objects and evaluates them against contextual constraints.

---

## Key Design Principles

### Capture First

Users should be able to dump tasks instantly without needing to organize them.

### Context Determines Priority

Priority should not be determined by due date alone.

Rozee evaluates multiple variables including:

- deadlines
- estimated duration
- dependencies
- cognitive difficulty
- schedule availability
- importance

### Reduce Cognitive Load

Instead of constantly deciding what to work on next, Rozee recommends the most appropriate task.

---

## Planned Workflow

1. Brain dump task input  
2. Task structuring  
3. Context integration with schedule  
4. Multi-factor prioritization  
5. Recommended next action  

---

## System Architecture (Early Concept)

Input Layer  
• text brain dump  
• task input interface  

Processing Layer  
• task parsing  
• task structuring  
• prioritization engine  

Data Layer  
• task storage  
• schedule data  
• user preferences  

Output Layer  
• ranked tasks  
• recommended next action  
• daily plan view  

---

## Future Capabilities

Planned features include:

- calendar integration
- AI-assisted task parsing
- dependency-aware prioritization
- duration-aware scheduling
- conversational task entry
- intelligent planning assistance

---

## Development Status

Rozee is currently in the early development stage.

The current focus is on building the core workflow:

brain dump → structured tasks → prioritized recommendations.

---

## Vision

Rozee is intended to become a **personal operations system** rather than just a task list.

Instead of simply storing tasks, the system will help users make better decisions about how to spend their time and energy.

---

## License

This project is currently under active development.
