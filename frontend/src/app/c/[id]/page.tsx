import { Suspense } from "react";

import { CollectionView } from "./CollectionView";

export default function CollectionPage() {
  return (
    <Suspense>
      <CollectionView />
    </Suspense>
  );
}
