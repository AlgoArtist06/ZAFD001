import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { AnswerView, type StructuredAnswer } from "@/components/answer-view";

// A grounded, normal answer: explanation, one verbatim-English citation, a
// practical next step, and the disclaimer with its legal-aid pointer.
const NORMAL: StructuredAnswer = {
  state: "normal",
  explanation: "In plain language, your question is about criminal law in India.",
  citations: [
    {
      reference: "Bharatiya Nyaya Sanhita (2023), Section 303",
      verbatim: "Whoever commits theft shall be punished with imprisonment.",
      url: "https://example.gov.in/bns/303",
    },
  ],
  nextStep: "Practical next step: read the cited provision and keep your evidence.",
  disclaimer:
    "This is legal information, not legal advice. For help, consult a lawyer or your nearest Legal Services Authority (NALSA / DLSA).",
};

// A high-stakes / emergency answer: the same grounded content, but it must lead
// with emergency and legal-aid contacts before the legal content.
const EMERGENCY: StructuredAnswer = {
  ...NORMAL,
  state: "emergency",
  highStakesNotice:
    "If you are in immediate danger or this is urgent, get help first:\n- Emergency (police / fire / ambulance): 112\n- Women's helpline: 181\n- Free legal aid: contact a lawyer or your nearest Legal Services Authority (NALSA / DLSA).",
};

// An out-of-scope / unsupported query: a graceful refusal, never a fabricated
// answer, still carrying the legal-aid pointer and disclaimer.
const REFUSAL: StructuredAnswer = {
  state: "refusal",
  explanation: "I do not have a sourced answer for that",
  citations: [],
  nextStep:
    "For help, consider contacting a lawyer or your nearest Legal Services Authority (NALSA / DLSA).",
  disclaimer:
    "This is legal information, not legal advice. For help, consult a lawyer or your nearest Legal Services Authority (NALSA / DLSA).",
};

describe("AnswerView", () => {
  it("renders the four structured parts: explanation, legal basis, next step, disclaimer", () => {
    render(<AnswerView answer={NORMAL} />);

    expect(screen.getByText(/In plain language/)).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: /legal basis/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Practical next step/)).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: /disclaimer/i }),
    ).toBeInTheDocument();
  });

  it("shows the citation in a distinct block with the statutory text verbatim in English", () => {
    render(<AnswerView answer={NORMAL} />);

    const basis = screen.getByRole("region", { name: /legal basis/i });
    expect(within(basis).getByText(/Section 303/)).toBeInTheDocument();
    const quote = within(basis).getByText(/Whoever commits theft/);
    expect(quote.tagName).toBe("BLOCKQUOTE");
    // The Citation Anchor stays court-traceable English even when the rest is not.
    expect(quote).toHaveAttribute("lang", "en");
  });

  it("leads a high-stakes answer with emergency and legal-aid contacts before the law", () => {
    render(<AnswerView answer={EMERGENCY} />);

    const emergency = screen.getByRole("alert");
    expect(within(emergency).getByText(/112/)).toBeInTheDocument();
    expect(within(emergency).getByText(/181/)).toBeInTheDocument();

    // The emergency contacts come before the legal basis in reading order.
    const basis = screen.getByRole("region", { name: /legal basis/i });
    expect(
      emergency.compareDocumentPosition(basis) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("renders an out-of-scope query as a graceful refusal, never a fabricated citation", () => {
    render(<AnswerView answer={REFUSAL} />);

    expect(
      screen.getByText(/I do not have a sourced answer for that/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: /legal basis/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the disclaimer and legal-aid pointer on every answer, including a refusal", () => {
    const { rerender } = render(<AnswerView answer={NORMAL} />);
    const normalDisclaimer = screen.getByRole("region", { name: /disclaimer/i });
    expect(normalDisclaimer).toHaveTextContent(/NALSA \/ DLSA/);

    rerender(<AnswerView answer={REFUSAL} />);
    const refusalDisclaimer = screen.getByRole("region", { name: /disclaimer/i });
    expect(refusalDisclaimer).toHaveTextContent(/NALSA \/ DLSA/);
  });

  it("marks each answer state so refusal, emergency, and normal are distinguishable", () => {
    const { container: normal } = render(<AnswerView answer={NORMAL} />);
    const { container: emergency } = render(<AnswerView answer={EMERGENCY} />);
    const { container: refusal } = render(<AnswerView answer={REFUSAL} />);

    const stateOf = (c: HTMLElement) =>
      c.querySelector("[data-answer-state]")?.getAttribute("data-answer-state");
    expect(stateOf(normal)).toBe("normal");
    expect(stateOf(emergency)).toBe("emergency");
    expect(stateOf(refusal)).toBe("refusal");
  });
});
