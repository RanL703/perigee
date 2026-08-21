import { useSyncExternalStore } from "react";

export type ChatTurn = {
  question: string;
  answer: string;
  source: "ollama" | "template";
  referencedEventIds: string[];
};

let turns: ChatTurn[] = [];
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

// Module-level store so the Ask Perigee conversation survives page
// navigation within the session without any reload.
export const chatStore = {
  get: (): ChatTurn[] => turns,
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  add(turn: ChatTurn): void {
    turns = [...turns, turn];
    emit();
  },
  history(limit = 6): { role: "user" | "assistant"; content: string }[] {
    return turns.slice(-limit).flatMap((turn) => [
      { role: "user" as const, content: turn.question },
      { role: "assistant" as const, content: turn.answer },
    ]);
  },
};

export function useChat(): ChatTurn[] {
  return useSyncExternalStore(chatStore.subscribe, chatStore.get);
}
