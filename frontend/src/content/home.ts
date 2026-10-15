export const COMMAND_QUESTIONS = [
  {
    question: "What is BTC doing?",
    answer: "No verified market data",
  },
  {
    question: "Is there an opportunity?",
    answer: "Not evaluated",
  },
  {
    question: "What does AI recommend?",
    answer: "Not evaluated",
  },
  {
    question: "What is my current risk?",
    answer: "No account risk on file",
  },
  {
    question: "Do I need to do anything?",
    answer: "Nothing in this build",
  },
] as const;

export const DEMO_PANELS = [
  {
    title: "BTC Market Status",
    value: "Sample session",
    detail: "No price, range, or trend is connected.",
  },
  {
    title: "AI View",
    value: "WAIT",
    detail: "Sample state for layout. No model has evaluated the market.",
  },
  {
    title: "Current Strategy",
    value: "Sample strategy",
    detail: "No strategy is saved or approved.",
  },
  {
    title: "Current Position",
    value: "Sample flat",
    detail: "No position is on file.",
  },
  {
    title: "Account Risk",
    value: "Sample band",
    detail: "No exposure has been calculated.",
  },
  {
    title: "Weekly Goal / Progress",
    value: "Sample objective",
    detail: "A goal is not an expected return. Nothing is tracked yet.",
  },
  {
    title: "Opportunity",
    value: "Sample card",
    detail: "This is not an opportunity and has no probability.",
  },
  {
    title: "Important Notification",
    value: "Sample notice",
    detail: "No alerts are connected.",
  },
] as const;
