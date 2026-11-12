export async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(path);
  }
  return response.json();
}
