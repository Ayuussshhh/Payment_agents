export default function Runs() {
  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Runs</p>
          <h1>A run can pause, resume, and stop.</h1>
        </div>
      </header>
      <section className="empty">
        <h2>Run history appears with a session.</h2>
        <p>Cancelling a run stops the agent at the next step. It does not void a payment. That separation is already in the engine.</p>
      </section>
    </>
  );
}
