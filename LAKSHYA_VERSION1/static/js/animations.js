(() => {
    const { gsap, ScrollTrigger, ScrollToPlugin } = window;
    if (!gsap || !ScrollTrigger) {
        document.documentElement.classList.remove('js-gsap');
        return;
    }

    gsap.registerPlugin(ScrollTrigger);
    if (ScrollToPlugin) {
        gsap.registerPlugin(ScrollToPlugin);
    }

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isSmallScreen = window.matchMedia('(max-width: 768px)').matches;
    const revealDistance = isSmallScreen ? 36 : 60;
    const cardDistance = isSmallScreen ? 26 : 40;
    const heroDistance = isSmallScreen ? 24 : 32;

    function createHeroEntrance() {
        const title = document.querySelector('.hero .hero-text h1');
        const subtext = document.querySelector('.hero .hero-text p');
        const buttons = gsap.utils.toArray('.hero .cta-btn');
        const visual = document.querySelector('.hero-visual');

        if (!title || !subtext || !buttons.length) return;

        const timeline = gsap.timeline({ defaults: { ease: 'power2.out' } });

        timeline
            .fromTo(
                title,
                { autoAlpha: 0, y: heroDistance },
                { autoAlpha: 1, y: 0, duration: 0.8 },
                0
            )
            .fromTo(
                subtext,
                { autoAlpha: 0, y: heroDistance * 0.85 },
                { autoAlpha: 1, y: 0, duration: 0.8 },
                0.2
            )
            .fromTo(
                buttons,
                { autoAlpha: 0, y: heroDistance * 0.7, scale: 0.95 },
                { autoAlpha: 1, y: 0, scale: 1, duration: 0.8, stagger: 0.1 },
                0.4
            );

        if (visual) {
            timeline.fromTo(
                visual,
                { autoAlpha: 0, y: heroDistance + 4, scale: 0.97 },
                { autoAlpha: 1, y: 0, scale: 1, duration: 0.9 },
                0.18
            );
        }
    }

    function createSectionReveals() {
        const sections = gsap.utils.toArray('section:not(.hero):not(.samples):not(.flow-preview)');

        sections.forEach(section => {
            const children = Array.from(section.children).filter(child => child.tagName !== 'SCRIPT');

            gsap.set(section, { autoAlpha: 0, y: revealDistance });
            if (children.length) {
                gsap.set(children, { autoAlpha: 0, y: revealDistance * 0.6 });
            }

            const timeline = gsap.timeline({
                scrollTrigger: {
                    trigger: section,
                    start: 'top 80%',
                    once: true
                }
            });

            timeline.to(section, {
                autoAlpha: 1,
                y: 0,
                duration: 0.8,
                ease: 'power2.out'
            });

            if (children.length) {
                timeline.to(
                    children,
                    {
                        autoAlpha: 1,
                        y: 0,
                        duration: 0.7,
                        ease: 'power2.out',
                        stagger: 0.12
                    },
                    0.06
                );
            }
        });
    }

    function createSamplesAnimation() {
        const samplesSection = document.querySelector('.samples');
        if (!samplesSection) return;

        const samplesHeading = samplesSection.querySelector('h2');
        const samplesSubtitle = samplesSection.querySelector('.subtitle');
        const cards = gsap.utils.toArray('.sample-card');

        if (samplesHeading) {
            gsap.set(samplesHeading, { autoAlpha: 0, y: revealDistance * 0.55 });
        }
        if (samplesSubtitle) {
            gsap.set(samplesSubtitle, { autoAlpha: 0, y: revealDistance * 0.45 });
        }
        if (cards.length) {
            gsap.set(cards, { autoAlpha: 0, y: cardDistance });
        }

        const timeline = gsap.timeline({
            scrollTrigger: {
                trigger: samplesSection,
                start: 'top 80%',
                once: true
            }
        });

        if (samplesHeading) {
            timeline.to(samplesHeading, {
                autoAlpha: 1,
                y: 0,
                duration: 0.8,
                ease: 'power2.out'
            });
        }

        if (samplesSubtitle) {
            timeline.to(
                samplesSubtitle,
                {
                    autoAlpha: 1,
                    y: 0,
                    duration: 0.8,
                    ease: 'power2.out'
                },
                samplesHeading ? 0.12 : 0
            );
        }

        if (cards.length) {
            timeline.to(
                cards,
                {
                    autoAlpha: 1,
                    y: 0,
                    duration: 0.8,
                    ease: 'power2.out',
                    stagger: 0.15
                },
                0.2
            );
        }
    }

    function createFlowSequence() {
        const flowSection = document.querySelector('.flow-preview');
        if (!flowSection) return;

        const flowHeader = flowSection.querySelector('.flow-header');
        const flowCard = flowSection.querySelector('.flow-card');
        const steps = gsap.utils.toArray('.flow-progress-step');
        if (!steps.length) return;

        const dots = steps.map(step => step.querySelector('.flow-progress-dot')).filter(Boolean);
        const labels = steps.map(step => step.querySelector('.flow-progress-label')).filter(Boolean);
        const lines = steps.map(step => step.querySelector('.flow-progress-line')).filter(Boolean);

        if (flowHeader) {
            gsap.set(flowHeader, { autoAlpha: 0, y: isSmallScreen ? 24 : 40 });
        }
        if (flowCard) {
            gsap.set(flowCard, { autoAlpha: 0, y: isSmallScreen ? 24 : 40 });
        }
        gsap.set(dots, { autoAlpha: 0, scale: 0.8 });
        gsap.set(labels, { autoAlpha: 0, y: isSmallScreen ? 10 : 14 });
        gsap.set(lines, { scaleX: 0, transformOrigin: 'left center' });

        const timeline = gsap.timeline({
            scrollTrigger: {
                trigger: flowSection,
                start: 'top 80%',
                once: true
            }
        });

        if (flowHeader) {
            timeline.to(flowHeader, {
                autoAlpha: 1,
                y: 0,
                duration: 0.5,
                ease: 'power2.out'
            });
        }

        if (flowCard) {
            timeline.to(
                flowCard,
                {
                    autoAlpha: 1,
                    y: 0,
                    duration: 0.5,
                    ease: 'power2.out'
                },
                flowHeader ? 0.08 : 0
            );
        }

        timeline.to(dots, {
            autoAlpha: 1,
            scale: 1,
            duration: 0.45,
            ease: 'power2.out',
            stagger: 0.14
        }, 0.12);

        timeline.to(
            labels,
            {
                autoAlpha: 1,
                y: 0,
                duration: 0.55,
                ease: 'power2.out',
                stagger: 0.14
            },
            0.05
        );

        timeline.to(
            lines,
            {
                scaleX: 1,
                duration: 0.55,
                ease: 'power2.out',
                stagger: 0.14,
                clearProps: 'transform'
            },
            0.08
        );
    }

    function setupCardHoverInteractions() {
        const canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
        if (!canHover) return;

        const previews = gsap.utils.toArray('.sample-preview');
        previews.forEach(preview => {
            preview.addEventListener('mouseenter', () => {
                gsap.to(preview, {
                    scale: 1.02,
                    duration: 0.3,
                    ease: 'power2.out',
                    boxShadow: '0 16px 34px rgba(17, 24, 39, 0.12)',
                    overwrite: 'auto'
                });
            });

            preview.addEventListener('mouseleave', () => {
                gsap.to(preview, {
                    scale: 1,
                    duration: 0.3,
                    ease: 'power2.out',
                    boxShadow: '0 0 0 rgba(17, 24, 39, 0)',
                    overwrite: 'auto'
                });
            });
        });
    }

    function setupButtonMicroInteractions() {
        const buttonSelector = [
            '.cta-btn',
            '.express-btn',
            '.sample-btn',
            '.hero-btn',
            '.flow-next-btn',
            '.submit-btn',
            '.demo-btn',
            '.pricing-btn'
        ].join(',');

        const buttons = gsap.utils.toArray(buttonSelector);
        if (!buttons.length) return;

        const canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

        buttons.forEach(button => {
            if (canHover) {
                button.addEventListener('mouseenter', () => {
                    const yOffset = button.classList.contains('hero-btn') ? -2 : -1;
                    gsap.to(button, {
                        scale: 1.02,
                        y: yOffset,
                        duration: 0.3,
                        ease: 'power2.out',
                        boxShadow: '0 12px 24px rgba(17, 24, 39, 0.18)',
                        overwrite: 'auto'
                    });
                });

                button.addEventListener('mouseleave', () => {
                    gsap.to(button, {
                        scale: 1,
                        y: 0,
                        duration: 0.3,
                        ease: 'power2.out',
                        boxShadow: '',
                        overwrite: 'auto'
                    });
                });
            }

            button.addEventListener('pointerdown', () => {
                gsap.to(button, {
                    scale: 0.96,
                    y: 0,
                    duration: 0.12,
                    ease: 'power2.out',
                    overwrite: 'auto'
                });
            });

            const resetPressState = () => {
                gsap.to(button, {
                    scale: canHover && button.matches(':hover') ? 1.02 : 1,
                    y: canHover && button.matches(':hover')
                        ? (button.classList.contains('hero-btn') ? -2 : -1)
                        : 0,
                    duration: 0.2,
                    ease: 'power2.out',
                    overwrite: 'auto'
                });
            };

            button.addEventListener('pointerup', resetPressState);
            button.addEventListener('pointercancel', resetPressState);
            button.addEventListener('blur', resetPressState);
        });
    }

    function setupNavbarScrollAnimation() {
        const header = document.querySelector('.site-header');
        const headerInner = document.querySelector('.header-inner');
        if (!header || !headerInner) return;

        let compact = false;

        const setCompact = (nextState) => {
            if (nextState === compact) return;
            compact = nextState;

            gsap.to(headerInner, {
                duration: 0.3,
                ease: 'power2.out',
                scale: compact ? 0.985 : 1,
                y: compact ? -1 : 0,
                backdropFilter: compact ? 'blur(16px) saturate(138%)' : 'blur(0px) saturate(100%)',
                WebkitBackdropFilter: compact ? 'blur(16px) saturate(138%)' : 'blur(0px) saturate(100%)',
                overwrite: 'auto'
            });
        };

        ScrollTrigger.create({
            start: 1,
            end: 'max',
            onUpdate: self => {
                if (self.scroll() <= 4) {
                    setCompact(false);
                    return;
                }

                if (self.direction === 1) {
                    setCompact(true);
                } else if (self.direction === -1) {
                    setCompact(false);
                }
            }
        });
    }

    function setupSmoothAnchorScroll() {
        const anchorLinks = gsap.utils.toArray('a[href^="#"]');
        if (!anchorLinks.length) return;

        anchorLinks.forEach(link => {
            if (link.closest('.site-nav')) return;

            const href = link.getAttribute('href');
            if (!href || href === '#') return;

            const target = document.querySelector(href);
            if (!target) return;

            link.addEventListener('click', event => {
                event.preventDefault();

                const headerHeight = document.querySelector('.site-header')?.offsetHeight || 0;

                if (ScrollToPlugin) {
                    gsap.to(window, {
                        duration: 0.9,
                        ease: 'power2.out',
                        scrollTo: {
                            y: target,
                            offsetY: headerHeight - 6,
                            autoKill: true
                        }
                    });
                } else {
                    const top = target.getBoundingClientRect().top + window.scrollY - headerHeight + 6;
                    window.scrollTo({ top, behavior: 'smooth' });
                }
            });
        });
    }

    function setupFaqAccordion() {
        const faqItems = gsap.utils.toArray('.faq-item');
        if (!faqItems.length) return;

        faqItems.forEach(item => {
            const button = item.querySelector('.faq-question');
            const answer = item.querySelector('.faq-answer');
            if (!button || !answer) return;

            button.addEventListener('click', () => {
                const isOpen = item.classList.contains('open');

                faqItems.forEach(otherItem => {
                    const otherButton = otherItem.querySelector('.faq-question');
                    const otherAnswer = otherItem.querySelector('.faq-answer');
                    if (!otherButton || !otherAnswer) return;

                    otherItem.classList.remove('open');
                    otherButton.setAttribute('aria-expanded', 'false');
                    otherAnswer.style.maxHeight = '0px';
                });

                if (isOpen) return;

                item.classList.add('open');
                button.setAttribute('aria-expanded', 'true');
                answer.style.maxHeight = `${answer.scrollHeight}px`;
            });
        });
    }

    function setupStatCounters() {
        const statValues = gsap.utils.toArray('.proof-stat-value[data-counter-target]');
        if (!statValues.length) return;

        const statSection = document.querySelector('.student-proof');
        if (!statSection) return;

        ScrollTrigger.create({
            trigger: statSection,
            start: 'top 78%',
            once: true,
            onEnter: () => {
                statValues.forEach(valueEl => {
                    const target = Number(valueEl.dataset.counterTarget || '0');
                    if (!Number.isFinite(target) || target <= 0) return;

                    const originalText = valueEl.textContent.trim();
                    const suffix = originalText.replace(/^[\d,\s]+/, '').trim();
                    const spacer = suffix && suffix !== '+' && suffix !== '%' ? ' ' : '';
                    const counter = { value: 0 };

                    gsap.to(counter, {
                        value: target,
                        duration: 1.4,
                        ease: 'power2.out',
                        onUpdate: () => {
                            valueEl.textContent = `${Math.round(counter.value)}${spacer}${suffix}`;
                        }
                    });
                });
            }
        });
    }

    function setupReducedMotionFallback() {
        const everything = gsap.utils.toArray(
            'section, .sample-card, .flow-item, .flow-progress-step, .flow-progress-dot, .flow-progress-label, .flow-progress-line, .flow-main-content'
        );
        gsap.set(everything, { clearProps: 'all' });
    }

    document.addEventListener('DOMContentLoaded', () => {
        setupFaqAccordion();

        if (prefersReducedMotion) {
            setupReducedMotionFallback();
            setupSmoothAnchorScroll();
            return;
        }

        createHeroEntrance();
        createSectionReveals();
        createSamplesAnimation();
        createFlowSequence();
        setupCardHoverInteractions();
        setupButtonMicroInteractions();
        setupNavbarScrollAnimation();
        setupSmoothAnchorScroll();
        setupStatCounters();

        ScrollTrigger.refresh();
    }, { once: true });

    window.addEventListener('load', () => {
        ScrollTrigger.refresh();
    }, { once: true });
})();
