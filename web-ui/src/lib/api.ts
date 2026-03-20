export async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message =
      data && typeof data === "object" && "message" in data
        ? String((data as { message: string }).message)
        : "Request failed";
    throw new Error(message);
  }

  return data as T;
}
