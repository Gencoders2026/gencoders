import api from "./api";

export async function analyzeMessage(
  query,
  personaHint = "",
  scenarioHint = ""
) {
  const response = await api.post("/analyze", {
    query,
    persona_hint: personaHint,
    scenario_hint: scenarioHint,
  });

  return response.data;
}