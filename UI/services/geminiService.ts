import { GoogleGenAI } from "@google/genai";

// FIX: Per @google/genai guidelines, initialize directly with the environment variable.
// Redundant checks and variables for API_KEY are removed as availability is assumed.
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

export async function generateResponse(documentContent: string, userQuery: string): Promise<string> {
  try {
    const model = 'gemini-2.5-flash';
    
    // FIX: Use systemInstruction for persona and task description, and contents for the user query.
    // This is a more structured and robust way to prompt the model.
    const systemInstruction = `You are an expert AI assistant specialized in analyzing and answering questions about documents.
Your task is to answer the user's question based *exclusively* on the content of the document provided below.
Do not use any external knowledge. If the answer is not found in the document, state that clearly.
Provide concise and accurate answers. Format your response using Markdown for better readability.`;

    const userPrompt = `--- DOCUMENT CONTENT ---
${documentContent}
--- END OF DOCUMENT ---

User's Question: ${userQuery}`;

    const response = await ai.models.generateContent({
      model: model,
      contents: userPrompt,
      config: {
        systemInstruction: systemInstruction,
      },
    });

    return response.text;
  } catch (error) {
    console.error("Error generating response from Gemini:", error);
    if (error instanceof Error) {
        return `Error: ${error.message}`;
    }
    return "An unexpected error occurred while processing your request.";
  }
}
