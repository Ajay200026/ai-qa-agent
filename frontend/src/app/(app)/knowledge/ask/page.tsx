"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Send } from "lucide-react";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/layout/page-header";
import type { AskCitation } from "@/lib/types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: AskCitation[];
}

const SUGGESTIONS = [
  "Explain this module",
  "Where is Finance_Type__c used?",
  "Which Apex classes update Account?",
  "Explain the Save button execution flow",
  "Show dependencies for the main LWC component",
  "What business rules exist?",
];

export default function KnowledgeAskPage() {
  const searchParams = useSearchParams();
  const moduleId = searchParams.get("module") || (typeof window !== "undefined" ? localStorage.getItem("knowledge_selected_module") : null);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: llmConfig } = useQuery({
    queryKey: ["llm-config"],
    queryFn: () => api.getLlmConfig(),
  });

  const ask = async (q: string) => {
    if (!moduleId || !q.trim() || streaming) return;
    const userMessage: ChatMessage = { role: "user", content: q.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setStreaming(true);

    let assistantContent = "";
    let citations: AskCitation[] = [];

    try {
      for await (const event of api.askKnowledgeStream(moduleId, q.trim())) {
        if (event.type === "citations" && event.citations) {
          citations = event.citations;
        } else if (event.type === "token" && event.content) {
          assistantContent += event.content;
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last?.role === "assistant") {
              updated[updated.length - 1] = { ...last, content: assistantContent, citations };
            } else {
              updated.push({ role: "assistant", content: assistantContent, citations });
            }
            return updated;
          });
        } else if (event.type === "error") {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `Error: ${event.message}` },
          ]);
        }
      }
      if (!assistantContent) {
        const result = await api.askKnowledge(moduleId, q.trim());
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: result.answer, citations: result.citations },
        ]);
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: e instanceof Error ? e.message : "Ask failed" },
      ]);
    } finally {
      setStreaming(false);
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  };

  if (!moduleId) {
    return (
      <div className="space-y-4">
        <PageHeader title="Ask AI" description="Select and scan a module from the Knowledge overview first." />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col space-y-4">
      <PageHeader
        title="Ask AI"
        description="Ask questions about your indexed Salesforce module using local Qwen via LM Studio."
      />

      <div className="flex flex-wrap gap-2">
        <Badge variant={llmConfig?.is_local ? "default" : "secondary"}>
          {llmConfig?.provider} {llmConfig?.model}
        </Badge>
        {!llmConfig?.enabled && (
          <Badge variant="destructive">LLM not available — start LM Studio</Badge>
        )}
      </div>

      <Card className="flex flex-1 flex-col overflow-hidden">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Conversation</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 space-y-4 overflow-y-auto pr-2">
            {messages.length === 0 && (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">Try asking:</p>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTIONS.map((s) => (
                    <Button key={s} variant="outline" size="sm" onClick={() => ask(s)}>
                      {s}
                    </Button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`rounded-lg p-3 text-sm ${
                  msg.role === "user" ? "ml-8 bg-primary text-primary-foreground" : "mr-8 bg-muted"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {msg.citations.map((c, j) => (
                      <Badge key={j} variant="secondary" className="text-xs">
                        {c.entity_type}: {c.name}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {streaming && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Thinking...
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form
            className="mt-4 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              ask(question);
            }}
          >
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about fields, LWCs, Apex, flows, navigation..."
              disabled={streaming}
            />
            <Button type="submit" disabled={streaming || !question.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Answers use indexed knowledge only — not the full repository.{" "}
        <Link href="/knowledge" className="underline">
          Back to Knowledge overview
        </Link>
      </p>
    </div>
  );
}
