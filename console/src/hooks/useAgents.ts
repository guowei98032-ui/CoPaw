import { useState, useEffect, useCallback } from "react";
import { agentsApi } from "../api/modules/agents";
import { useAppMessage } from "./useAppMessage";
import type { AgentSummary } from "../api/types/agents";

export function useAgents() {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const { message } = useAppMessage();

  const loadAgents = useCallback(async () => {
    setLoading(true);
    try {
      const response = await agentsApi.listAgents();
      setAgents(response.agents);
    } catch (error: any) {
      console.error("Failed to load agents:", error);
      message.error(error.message || "Failed to load agents");
      setAgents([]);
    } finally {
      setLoading(false);
    }
  }, [message]);

  const deleteAgent = useCallback(async (agentId: string) => {
    try {
      await agentsApi.deleteAgent(agentId);
      setAgents((prev) => prev.filter((a) => a.id !== agentId));
    } catch (error: any) {
      console.error("Failed to delete agent:", error);
      message.error(error.message || "Failed to delete agent");
      throw error;
    }
  }, [message]);

  const toggleAgent = useCallback(async (agentId: string, enabled: boolean) => {
    try {
      await agentsApi.toggleAgentEnabled(agentId, enabled);
      setAgents((prev) =>
        prev.map((a) =>
          a.id === agentId ? { ...a, enabled } : a
        )
      );
    } catch (error: any) {
      console.error("Failed to toggle agent:", error);
      message.error(error.message || "Failed to toggle agent");
      throw error;
    }
  }, [message]);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  return {
    agents,
    loading,
    deleteAgent,
    toggleAgent,
    loadAgents,
  };
}
