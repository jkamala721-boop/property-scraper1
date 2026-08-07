const axios = require("axios");
const cheerio = require("cheerio");

async function getPage() {

    const response = await axios.get(
        "https://www.buyrentkenya.com/flats-apartments-for-sale/nairobi/kileleshwa",
        {
            headers: {
                "User-Agent":
                "Mozilla/5.0"
            },
            timeout: 60000
        }
    );

    return response.data;
}


async function scrape(){

    let html;

try {
    html = await getPage();
}
catch(error){
    console.log("Download failed:", error.message);
    return;
}

    const $ = cheerio.load(html);

    console.log("Looking for property links...");


    $("a").each((index, element)=>{

        const href = $(element).attr("href");

        if(href && href.includes("/property/")){

            console.log("PROPERTY LINK:");
            console.log(href);

        }

    });

}


scrape();
