import {createContext, useCallback, useContext, useLayoutEffect} from 'react';
import {useLocation, useRouteMatch} from 'react-router-dom';
import {atom, useRecoilValue, useSetRecoilState} from 'recoil';

import {CloudOSSContext} from './CloudOSSContext';
import {useDangerousRenderEffect} from '../hooks/useDangerousRenderEffect';

export const currentPageAtom = atom<{path: string; specificPath: string}>({
  key: 'currentPageAtom',
  default: {path: '/', specificPath: '/'},
});

export interface GenericAnalytics {
  group?: (groupId: string, traits?: Record<string, any>) => void;
  identify?: (userId: string, traits?: Record<string, any>) => void;
  page: (path: string, specificPath: string) => void;
  track: (eventName: string, properties?: Record<string, any>) => void;
}

export const AnalyticsContext = createContext<GenericAnalytics>(undefined!);

const PAGEVIEW_DELAY = 300;

export const usePageContext = () => {
  return useRecoilValue(currentPageAtom);
};

const useAnalytics = () => {
  const analytics = useContext(AnalyticsContext);
  if (!analytics && typeof 'jest' === undefined && !process.env.STORYBOOK) {
    throw new Error('Analytics may only be used within `AnalyticsContext.Provider`.');
  }
  return analytics;
};

export const dummyAnalytics = () => ({
  group: (groupId: string, traits?: Record<string, any>) => {
    if (process.env.NODE_ENV !== 'production') {
      console.log('[Group]', groupId, traits);
    }
  },
  identify: (id: string, traits?: Record<string, any>) => {
    if (process.env.NODE_ENV !== 'production') {
      console.log('[Identify]', id, traits);
    }
  },
  page: (path: string, specificPath: string) => {
    if (process.env.NODE_ENV !== 'production') {
      console.log('[Pageview]', {path, specificPath});
    }
  },
  track: (eventName: string, properties?: Record<string, any>) => {
    if (process.env.NODE_ENV !== 'production') {
      console.log('[Event]', eventName, properties);
    }
  },
});

export const useTrackPageView = () => {
  const analytics = useAnalytics();
  const match = useRouteMatch();
  const {pathname: specificPath} = useLocation();
  const {path} = match;

  const setCurrentPage = useSetRecoilState(currentPageAtom);

  useLayoutEffect(() => {
    // Wait briefly to allow redirects.
    const timer = setTimeout(() => {
      analytics.page(path, specificPath);
    }, PAGEVIEW_DELAY);
    setCurrentPage({path, specificPath});

    return () => {
      clearTimeout(timer);
    };
  }, [analytics, path, setCurrentPage, specificPath]);

  const {onViewChange} = useContext(CloudOSSContext);

  useDangerousRenderEffect(() => {
    // Update Cloud synchronously that the view is changing in order to
    // better capture the dependencies of the view
    onViewChange({path});
  }, [path]);
};

export const useTrackEvent = () => {
  const analytics = useAnalytics();
  const match = useRouteMatch();
  const {pathname: specificPath} = useLocation();
  const {path} = match;

  return useCallback(
    (eventName: string, properties?: Record<string, any>) => {
      analytics.track(eventName, {...properties, path, specificPath});
    },
    [analytics, path, specificPath],
  );
};
