export default function BetaBanner() {
  return (
    <div className="w-full bg-blue-700">
      <div className="mx-auto max-w-7xl px-4 py-2.5 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-center gap-2 text-center sm:gap-3">
          <span className="inline-flex items-center rounded-md bg-white px-2 py-0.5 text-xs font-black uppercase tracking-wider text-blue-700">
            EARLY BETA
          </span>
          <p className="text-xs font-bold leading-tight text-white sm:text-sm">
            Free during beta. Live processing is improving quickly, and demo results are clearly labelled.
          </p>
        </div>
      </div>
    </div>
  );
}
