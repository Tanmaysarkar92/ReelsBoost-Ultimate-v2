def upload_to_youtube(
    video_path,
    title=None,
    description=None,
    tags=None
):
    """Upload an MP4 video to YouTube with dynamic metadata."""

    try:

        # ====================================================
        # STEP 1 - CHECK VIDEO
        # ====================================================

        if not video_path or not os.path.exists(video_path):

            logger.error(
                f"❌ YouTube: Video not found: {video_path}"
            )

            return False

        # ====================================================
        # STEP 2 - GET YOUTUBE SERVICE
        # ====================================================

        youtube = get_youtube_service()

        if youtube is None:

            logger.error(
                "❌ YouTube service unavailable"
            )

            return False

        # ====================================================
        # STEP 3 - DYNAMIC YOUTUBE METADATA
        # ====================================================

        if not title or not description:

            # Use the video filename to create a stable variation.
            filename = os.path.basename(video_path)

            # Remove extension and clean common generated names.
            video_name = os.path.splitext(filename)[0]

            # Create a small deterministic index so repeated
            # uploads don't always use the exact same wording.
            variation_index = (
                sum(ord(char) for char in video_name)
                % 8
            )

            title_variations = [

                "🏠 This Property Is Seriously Worth Seeing! #Shorts",

                "🏡 Would You Live In This Property? #Shorts",

                "✨ A Property Tour You Don't Want To Miss! #Shorts",

                "🔥 One Property, So Many Possibilities! #Shorts",

                "🏠 Take A Look Inside This Amazing Property! #Shorts",

                "💰 Is This Your Next Dream Property? #Shorts",

                "🏡 Another Interesting Property Tour! #Shorts",

                "👀 Wait Until You See This Property! #Shorts"
            ]

            description_variations = [

                "🏠 Take a quick look at this interesting property.\n\n"
                "From the location to the overall property appeal, "
                "there is always something interesting to discover.\n\n"
                "📩 Want property details? Contact us for more information.\n\n"
                "🔔 Subscribe to Sarkar Robotics for more AI-powered "
                "property tours, real estate stories and interesting visuals.\n\n"
                "#Shorts #RealEstate #Property #PropertyTour #SarkarRobotics",

                "🏡 Discover another interesting real estate property.\n\n"
                "This short video gives you a quick visual look at the property "
                "and its potential.\n\n"
                "📩 Contact us for property details and availability.\n\n"
                "🔔 Subscribe for more property tours and AI-powered real estate content.\n\n"
                "#Shorts #RealEstate #Property #RealEstateIndia #SarkarRobotics",

                "✨ What do you think about this property?\n\n"
                "Watch the full short and explore the space, design and overall feel.\n\n"
                "📩 For more information about the property, get in touch with us.\n\n"
                "🔔 Follow Sarkar Robotics for more interesting property videos.\n\n"
                "#Shorts #Property #RealEstate #PropertyForSale #SarkarRobotics",

                "🔥 Another property worth a quick look!\n\n"
                "Real estate can look very different from property to property. "
                "Here is another one to explore.\n\n"
                "📩 Interested? Contact us for more details.\n\n"
                "🔔 Subscribe to Sarkar Robotics for more real estate visuals and stories.\n\n"
                "#Shorts #RealEstate #PropertyTour #LuxuryProperty #SarkarRobotics"
            ]

            if not title:
                title = title_variations[variation_index]

            if not description:
                description = description_variations[
                    variation_index % len(description_variations)
                ]

        # ====================================================
        # STEP 4 - DEFAULT TAGS
        # ====================================================

        if tags is None:

            tags = [
                "real estate",
                "property",
                "property tour",
                "property for sale",
                "real estate india",
                "house tour",
                "luxury property",
                "real estate property",
                "property listing",
                "Sarkar Robotics"
            ]

        # ====================================================
        # STEP 5 - VIDEO METADATA
        # ====================================================

        body = {

            "snippet": {

                "title": title[:100],

                "description": description[:5000],

                "tags": tags,

                "categoryId": "22"
            },

            "status": {

                "privacyStatus": "public",

                "selfDeclaredMadeForKids": False
            }
        }

        # ====================================================
        # STEP 6 - UPLOAD
        # ====================================================

        logger.info(
            f"▶️ YouTube upload started..."
        )

        logger.info(
            f"🎯 YouTube title: {title}"
        )

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True
        )

        request = youtube.videos().insert(

            part="snippet,status",

            body=body,

            media_body=media
        )

        response = request.execute()

        # ====================================================
        # STEP 7 - RESULT
        # ====================================================

        video_id = response.get("id")

        if video_id:

            logger.info(
                f"✅ YouTube upload successful: "
                f"{video_id}"
            )

            logger.info(
                f"🔗 https://www.youtube.com/watch?v={video_id}"
            )

            return True

        logger.error(
            "❌ YouTube upload completed but no video ID returned"
        )

        return False

    except Exception as e:

        logger.exception(
            f"❌ YouTube upload error: {e}"
        )

        return False