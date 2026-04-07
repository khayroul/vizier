import { Refine } from "@refinedev/core";
import dataProvider from "@refinedev/simple-rest";
import routerProvider from "@refinedev/react-router";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/Layout";
import { HomePage } from "./pages/Home";
import { JobsPage } from "./pages/Jobs";
import { TokenSpendPage } from "./pages/TokenSpend";
import { FeedbackPage } from "./pages/Feedback";
import { PipelinePage } from "./pages/Pipeline";
import { DesignSelectorPage } from "./pages/DesignSelector";

const API_URL = "/api";

export function App() {
  return (
    <BrowserRouter>
      <Refine
        dataProvider={dataProvider(API_URL)}
        routerProvider={routerProvider}
        resources={[
          { name: "home", list: "/" },
          { name: "v_job_traces", list: "/jobs" },
          { name: "v_token_spend_daily", list: "/token-spend" },
          { name: "feedback", list: "/feedback" },
          { name: "v_pipeline_detail", list: "/pipeline" },
          { name: "design-selector", list: "/design-selector" },
        ]}
        options={{ disableTelemetry: true }}
      >
        <Layout>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/token-spend" element={<TokenSpendPage />} />
            <Route path="/feedback" element={<FeedbackPage />} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route path="/design-selector" element={<DesignSelectorPage />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </Layout>
      </Refine>
    </BrowserRouter>
  );
}
