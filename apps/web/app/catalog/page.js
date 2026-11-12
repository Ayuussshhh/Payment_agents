"use client";

import { useEffect, useState } from "react";
import { apiGet } from "../../lib/api";

export default function Catalog() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet("/v1/catalog")
      .then((data) => setItems(data.catalog || []))
      .catch((caught) => setError(caught.message));
  }, []);

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Merchant catalog</p>
          <h1>The data the agent shops from.</h1>
        </div>
      </header>
      <p className="lede">
        Prices and specs live here, not in the model. The engine recomputes every cart from these fields, so a product whose
        description tries to manipulate the agent can never change what is charged.
      </p>

      {error ? <p className="banner">{error}</p> : null}

      {items === null ? (
        <div className="catalog-grid">
          {[0, 1, 2, 3, 4, 6].map((i) => (
            <article key={i} className="product skeleton" />
          ))}
        </div>
      ) : (
        <div className="catalog-grid">
          {items.map((product) => (
            <article key={product.sku} className="product">
              <div className="product-top">
                <strong>{product.name || product.sku}</strong>
                <span className="price">${(product.unit_amount_minor / 100).toFixed(0)}</span>
              </div>
              <div className="chips">
                <span className="chip">{product.brand}</span>
                <span className="chip">{product.ram_gb} GB</span>
                <span className="chip">
                  {product.storage_gb} GB {product.storage_type}
                </span>
              </div>
              <p className="product-desc">{product.description}</p>
              <code className="product-sku">{product.sku}</code>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
