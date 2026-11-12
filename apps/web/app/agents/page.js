export default function Agents() {
  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Agents</p>
          <h1>Published versions, not a draft text box.</h1>
        </div>
      </header>
      <section className="empty">
        <h2>No session is connected.</h2>
        <p>Creating an agent requires a signed-in membership. The engine already accepts a published version with a frozen prompt, model, and skill list.</p>
      </section>
    </>
  );
}
