export async function fetchAppConfig() {
  const response = await fetch("/api/app-config");
  if (!response.ok) {
    throw new Error(`Unable to load app config (${response.status})`);
  }
  return response.json();
}
