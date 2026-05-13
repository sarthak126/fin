import Navbar from "@/components/landing/Navbar";
import HeroSection from "@/components/landing/HeroSection";
import CredibilityMetrics from "@/components/landing/CredibilityMetrics";
import ProductPreview from "@/components/landing/ProductPreview";
import HowItWorksSection from "@/components/landing/HowItWorksSection";
import SecuritySection from "@/components/landing/SecuritySection";
import SocialProofSection from "@/components/landing/SocialProofSection";
import CTASection from "@/components/landing/CTASection";
import Footer from "@/components/landing/Footer";

export default function Home() {
  return (
    <main className="relative min-h-screen bg-background overflow-hidden">
      <Navbar />
      <HeroSection />
      <CredibilityMetrics />
      <ProductPreview />
      <HowItWorksSection />
      <SecuritySection />
      <SocialProofSection />
      <CTASection />
      <Footer />
    </main>
  );
}
