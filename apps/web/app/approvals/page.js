export default function Approvals() {
  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Approvals</p>
          <h1>One cart. One signature.</h1>
        </div>
      </header>
      <section className="empty">
        <h2>No session is connected.</h2>
        <p>
          An approval binds the person to the exact cart that was evaluated. If a line changes, that approval is no
          longer valid.
        </p>
      </section>
    </>
  );
}
