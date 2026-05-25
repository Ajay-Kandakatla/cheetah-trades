/* usePageContext — shared state for "what is the user currently looking at?"
 *
 *  The floating ChatWidget reads from this context so it can pass the
 *  current page's data to Claude. Each page is expected to call
 *  setPageContext() in a useEffect when it mounts/updates, with the
 *  structured snapshot it wants the AI assistant to know about.
 *
 *  Schema is intentionally loose ({ page: string, ...rest }) so each
 *  page can shape its context however makes sense — there's no upfront
 *  schema we'd want to mandate across SEPA detail / Setups / Chatter /
 *  Catalysts, etc.
 *
 *  Typical use from a page:
 *
 *    const { setPageContext } = usePageContext();
 *    useEffect(() => {
 *      setPageContext({
 *        page:        'sepa-detail',
 *        symbol:      'MU',
 *        score:       data?.score,
 *        rs_rank:     data?.rs_rank,
 *        stage_label: data?.stage?.label,
 *        entry_setup: data?.entry_setup,
 *      });
 *      return () => setPageContext(null);   // clear on unmount
 *    }, [data, setPageContext]);
 *
 *  Why a context rather than a global module variable? React state
 *  ensures the ChatWidget re-renders when context changes (a plain
 *  module-level var doesn't trigger re-renders).
 */
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

export type PageContextValue = {
  page?: string;
  [key: string]: unknown;
} | null;

type CtxShape = {
  context:        PageContextValue;
  setPageContext: (v: PageContextValue) => void;
};

const PageContextCtx = createContext<CtxShape>({
  context:        null,
  setPageContext: () => {},
});

export function PageContextProvider({ children }: { children: ReactNode }) {
  const [context, setContext] = useState<PageContextValue>(null);
  // useCallback so setPageContext has a stable identity — callers
  // typically pass it as a useEffect dep, and a fresh function every
  // render would loop their effect.
  const setPageContext = useCallback((v: PageContextValue) => {
    setContext(v);
  }, []);
  return (
    <PageContextCtx.Provider value={{ context, setPageContext }}>
      {children}
    </PageContextCtx.Provider>
  );
}

export function usePageContext(): CtxShape {
  return useContext(PageContextCtx);
}
