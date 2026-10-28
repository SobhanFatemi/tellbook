// Group matching purchased units, preserving edition/product and price identity.
export function groupOrderItems(items = []) {
  const groups = new Map();
  for (const item of items) {
    const contents = item.contents || [];
    const key = JSON.stringify([item.product_id ?? null, item.title, contents]);
    if (!groups.has(key)) groups.set(key, { ...item, key, contents, quantity: 0, total: 0, pendingIndices: [], readyCount: 0, uniformPrice: true });
    const group = groups.get(key);
    group.uniformPrice = group.uniformPrice && Number(group.price) === Number(item.price);
    group.quantity++;
    group.total += Number(item.price);
    if (item.status === 'awaiting_sourcing') group.pendingIndices.push(item.index);
    else if (item.status !== 'failed') group.readyCount++;
  }
  return [...groups.values()];
}
