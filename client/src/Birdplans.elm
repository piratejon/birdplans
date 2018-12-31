{-
Birdplans.elm
2018-12-27
jonathanwesleystone+KI5BEX@gmail.com

Web 2.0 Birdplans client
-}

module Birdplans exposing (main)

import Browser
import List
import Http

import Task -- set current time <https://stackoverflow.com/a/52156804/5403184> 2018-12-30
import Time

import Tuple exposing (first, second)
import String exposing (length, toUpper, slice)

import Html.Attributes as Attr
import Html.Events exposing (..)
import Html exposing (..)

import Json.Decode as JsonD
import Json.Encode as JsonE
import Url.Builder as UrlB
import Url

import Char exposing (toCode, fromCode)

birdsUrl = "/birds.json"
zonesUrl = "/tz.json"

type Msg
  = Search
  | UpdateGrid String
  | UpdateGridRef String
  | UpdateLat String
  | UpdateLng String
  | UpdateAlt String
  | UpdateTimeZone String
  | UpdateDateTime String
  | ReceiveBirds (Result Http.Error (List String))
  | ReceiveTimeZones (Result Http.Error (List String))
  | ReceivePasses (Result Http.Error (List Pass))
  | UpdateBirds String
  | SetTimeZone Time.Zone
  | SetTimeZoneName Time.ZoneName
  | SetTimeNow Time.Posix

main =
  Browser.element
  { init = init
  , update = update
  , subscriptions = subscriptions
  , view = view
  }

type LocatorSelectorType
  = GridCenter
  | GridNW
  | GridNE
  | GridSW
  | GridSE
  | LatLng

toString : LocatorSelectorType -> String
toString locator =
  case locator of
    GridCenter -> "GridCenter"
    GridNW -> "GridNW"
    GridNE -> "GridNE"
    GridSW -> "GridSW"
    GridSE -> "GridSE"
    LatLng -> "LatLng"

type alias Bird =
  { name : String
  , selected : Bool
  }

type alias State =
  { locator_selector : LocatorSelectorType
  , lat : Float
  , lng : Float
  , lattxt : String
  , lngtxt : String
  , grid : String
  , grid_valid : Bool
  , lat_valid : Bool
  , lng_valid : Bool
  , min_alt : Int
  , min_alt_txt : String
  , min_alt_valid : Bool
  , birds : List Bird
  , query_string : String
  , datetime : String
  , datetime_valid : Bool
  , timezone : Time.Zone
  , timezonename : String
  , timezones : List String
  }

type alias PassAzimuth =
  { aos : Float
  , tca : Float
  , los : Float
  }

type alias PassTime =
  { aos : Int
  , tca : Int
  , los : Int
  }

type alias Pass =
  { grid: String
  , lat : Float
  , lng : Float
  , bird : String
  , azimuth : PassAzimuth
  , time : PassTime
  }

subscriptions : State -> Sub Msg
subscriptions state =
  Sub.none

init : () -> (State, Cmd Msg)
init _ = (
  initialState
  , Cmd.batch
    [ getAvailableBirds birdsUrl
    , getAvailableTimeZones zonesUrl
    , Task.perform SetTimeZone Time.here
    ]
  )

initialState : State
initialState =
  let
      grid = "EM15gj"
      latlng = Maybe.withDefault (35.375, -97.5) (gridToLatLng grid)
      lat = first latlng
      lng = second latlng
      min_alt = 12
  in 
      { locator_selector = GridSW
      , lat = lat
      , lng = lng
      , lattxt = String.fromFloat lat
      , lngtxt = String.fromFloat lng
      , grid = grid
      , grid_valid = True
      , lat_valid = True
      , lng_valid = True
      , min_alt_valid = True
      , min_alt = min_alt
      , min_alt_txt = String.fromInt min_alt
      , birds = []
      , query_string = "query_string"
      , datetime = ""
      , datetime_valid = True
      , timezone = Time.utc
      , timezonename = "UTC"
      , timezones = []
      }

view : State -> Html Msg
view state =
  div [] [
    h1 [] [text "birdplans"]
    , div []
      [ section [ Attr.id "locators" ]
        [ viewInput "Grid" "text" initialState.grid state.grid (if state.grid_valid then "valid" else "invalid") UpdateGrid
        {-
        , radioInput "Center" "gridref" "GridCenter" state.locator_selector UpdateGridRef
        , radioInput "NW" "gridref" "GridNW" state.locator_selector UpdateGridRef
        , radioInput "NE" "gridref" "GridNE" state.locator_selector UpdateGridRef
        , radioInput "SW" "gridref" "GridSW" state.locator_selector UpdateGridRef
        , radioInput "SE" "gridref" "GridSE" state.locator_selector UpdateGridRef
        -}
        , viewInput "Latitude" "text" initialState.lattxt state.lattxt (if state.lat_valid then "valid" else "invalid") UpdateLat
        , viewInput "Longitude" "text"  initialState.lngtxt state.lngtxt (if state.lng_valid then "valid" else "invalid") UpdateLng
        , viewInput "Start of 7-day window to search" "datetime-local" initialState.datetime state.datetime (if state.datetime_valid then "valid" else "invalid") UpdateDateTime
        , viewSelect "Time Zone" state.timezonename state.timezones UpdateTimeZone
        , viewInput "Minimum Degrees Altitude" "text" initialState.min_alt_txt state.min_alt_txt (if state.min_alt_valid then "valid" else "invalid") UpdateAlt
        , viewChecks "Birds" state.birds UpdateBirds
        ]
        , input [ Attr.type_ "button", Attr.value "Search", onClick Search ] []
        , text state.query_string
      ]
    , Html.node "link" [ Attr.rel "stylesheet", Attr.href "birdplans.css" ] []
  ]

birdCheck : Bird -> (String -> Msg) -> Html Msg
birdCheck bird toMsg =
  label [ Attr.class (if bird.selected then "bird_checked" else "bird_unchecked") ]
    [ text bird.name
    , input
      [ Attr.type_ "checkbox"
      , Attr.value bird.name
      , Attr.checked bird.selected
      , onInput toMsg
      ] []
    ]

viewSelect : String -> String -> (List String) -> (String -> Msg) -> Html Msg
viewSelect label_ value options toMsg =
  label []
    [ (span [] [text label_])
    , select [ on "change" (JsonD.map toMsg targetValue), onInput toMsg ] (
      List.map (\i -> option
        [ Attr.value i
        , Attr.selected (i == value)
        ] [ text i ]) options
      )
    ]

viewChecks : String -> (List Bird) -> (String -> Msg) -> Html Msg
viewChecks label_ birds toMsg =
  div [] (
    [div [] [text label_]]
    ++ List.map (\b -> (birdCheck b toMsg)) birds
    {-
    ++ List.map (\b -> (birdCheck b toMsg)) (List.filter (\b -> b.selected) birds)
    ++ [ div [] [] ]
    ++ List.map (\b -> (birdCheck b toMsg)) (List.filter (\b -> not b.selected) birds)
    -}
  )

viewInput : String -> String -> String -> String -> String -> (String -> Msg) -> Html Msg
viewInput label_ type_ placeholder_ value_ class toMsg =
  label []
    [ (span [] [text label_])
    , input
      [ Attr.type_ type_
      , Attr.placeholder placeholder_
      , Attr.value value_
      , Attr.class class
      , onInput toMsg ]
      []
    ]

radioInput : String -> String -> String -> LocatorSelectorType -> String -> (String -> Msg) -> Html Msg
radioInput label_ name value selected class toMsg =
  label []
    [ (span [] [text label_])
    , input
      [ Attr.type_ "radio"
      , Attr.name name
      , Attr.value value
      , Attr.checked ((toString selected) == value)
      , Attr.class class
      , onInput toMsg ]
      []
    ]

addFloatTuple : (Float, Float) -> (Float, Float) -> (Float, Float)
addFloatTuple (a, b) (c, d) =
  (a + c, b + d)

isBetween left middle right = (left <= middle) && (middle <= right)
twoBetweens left right mid0 mid1 = (isBetween left mid0 right) && (isBetween left mid1 right)

decodeField : Int -> Int -> Maybe (Float, Float)
decodeField a b =
  if (twoBetweens (toCode 'A') (toCode 'R') a b)
  then
    Just (
      addFloatTuple
        (-90.0, -180.0)
        (toFloat (b - 0x41) * 10.0, toFloat (a - 0x41) * 20.0)
    )
  else
    Nothing

decodeSquare : Int -> Int -> Int -> Int -> Maybe (Float, Float)
decodeSquare a b c d =
  case (decodeField a b) of
    Nothing -> Nothing
    Just (a_, b_) ->
      if (twoBetweens (toCode '0') (toCode '9') c d)
      then
        Just (
          addFloatTuple
            (a_, b_)
            (toFloat (d - 0x30) * 1.0, toFloat (c - 0x30) * 2.0)
        )
      else
        Nothing

decodeSubsquare a b c d e f =
  case (decodeSquare a b c d) of
    Nothing -> Nothing
    Just (c_, d_) ->
      if (twoBetweens (toCode 'A') (toCode 'X') e f)
      then
        Just (
          addFloatTuple
            (c_, d_)
            (toFloat (f - 0x41) * 2.5 / 60.0, toFloat (e - 0x41) * 5.0 / 60.0)
        )
      else
        Nothing

decodeExtendedSquare a b c d e f g h =
  case (decodeSubsquare a b c d e f) of
    Nothing -> Nothing
    Just (e_, f_) ->
      if (twoBetweens (toCode '0') (toCode '9') g h)
      then
        Just (
          addFloatTuple
            (e_, f_)
            (toFloat (h - 0x30) * 2.5 / 600.0, toFloat (g - 0x30) * 5.0 / 600.0)
        )
      else
        Nothing

gridToLatLng : String -> Maybe (Float, Float)
gridToLatLng grid =
  let ords = (List.map toCode (String.toList (toUpper grid))) in
    case ords of
      [a, b] -> decodeField a b
      [a, b, c, d] -> decodeSquare a b c d
      [a, b, c, d, e, f] -> decodeSubsquare a b c d e f
      [a, b, c, d, e, f, g, h] -> decodeExtendedSquare a b c d e f g h
      _ -> Nothing

latLngToGrid : Float -> Float -> String
latLngToGrid lat lng =
  let
      lng_z = lng + 180.0
      a = floor (lng_z / 20.0)
      a_20_rem = lng_z - (20.0 * (toFloat a))
      c = floor (a_20_rem / 2.0)
      c_2_rem = a_20_rem - (2.0 * (toFloat c))
      e = floor (c_2_rem * 12.0)

      lat_z = lat + 90.0
      b = floor (lat_z / 10.0)
      b_20_rem = lat_z - (10.0 * (toFloat b))
      d = floor (b_20_rem / 1.0)
      d_2_rem = b_20_rem - (1.0 * (toFloat d))
      f = floor (d_2_rem * 24.0)
  in
      String.fromList
        (List.map fromCode
          [ a + 0x41
          , b + 0x41
          , c + 0x30
          , d + 0x30
          , e + 0x61
          , f + 0x61
          ]
        )

-- some tests
-- "EM15gj00" = latLngToGrid 35.375 -97.5

update : Msg -> State -> (State, Cmd Msg)
update msg state =
  let _ = Debug.log "msg" msg in
  case msg of
    Search -> ({state | query_string = buildQueryString state}, Cmd.none)

    UpdateGridRef _ -> (state, Cmd.none)

    UpdateLat newlat ->
      case (String.toFloat newlat) of
        Just lat ->
          if (isBetween -90.0 lat 90.0)
          then
            ({state
              | lattxt = newlat
              , lat_valid = True
              , lat = lat
              , grid = (if state.lng_valid then (latLngToGrid lat state.lng) else state.grid)
              , grid_valid = state.lng_valid
            }, Cmd.none)
          else
            ({state | lattxt = newlat, lat_valid = False}, Cmd.none)
        Nothing -> ({state | lattxt = newlat, lat_valid = False}, Cmd.none)

    UpdateLng newlng ->
      case (String.toFloat newlng) of
        Just lng ->
          if (isBetween -180.0 lng 180.0)
          then
            ({state
              | lngtxt = newlng
              , lng_valid = True
              , lng = lng
              , grid = (if state.lat_valid then (latLngToGrid state.lat lng) else state.grid)
              , grid_valid = state.lat_valid
            }, Cmd.none)
          else
            ({state | lngtxt = newlng, lng_valid = False}, Cmd.none)
        Nothing -> ({state | lngtxt = newlng, lng_valid = False}, Cmd.none)

    UpdateGrid grid ->
        case (gridToLatLng grid) of
          Just latlng ->
            let
                lat = first latlng
                lng = second latlng
            in
                ({state
                  | grid = grid
                  , grid_valid = True
                  , lat = lat
                  , lng = lng
                  , lattxt = String.fromFloat lat
                  , lngtxt = String.fromFloat lng
                  , lat_valid = True
                  , lng_valid = True
                }, Cmd.none)
          Nothing -> ({state | grid = grid, grid_valid = False}, Cmd.none)

    UpdateAlt alt_txt ->
      case (String.toInt alt_txt) of
        Just alt -> (
          {state
          | min_alt_txt = alt_txt
          , min_alt = alt
          , min_alt_valid = True
          }, Cmd.none)
        Nothing -> ({state | min_alt_valid = False, min_alt_txt = alt_txt}, Cmd.none)

    ReceiveBirds result ->
      case result of
        Err _ -> (state, Cmd.none)
        Ok birds -> ({state | birds = List.map (\b -> {name=b, selected=False}) (List.sort birds)}, Cmd.none)

    ReceiveTimeZones result ->
      case result of
        Err _ -> (state, Cmd.none)
        Ok zones -> ({state | timezones = List.sort zones}, Cmd.none)

    UpdateBirds bird ->
      let _ = Debug.log "updatebirds" bird in
      ({state
        | birds = (List.sortWith selectedBirdSorter (List.sortBy .name (List.map (\b -> if b.name == bird then {b | selected = (not b.selected)} else b) state.birds)))}, Cmd.none)

    ReceivePasses result ->
      case result of
        Err _ -> (state, Cmd.none)
        Ok passes -> let _ = Debug.log "receivepasses" passes in (state, Cmd.none)

    SetTimeZone zone ->
      ({ state | timezone = zone}, Task.perform SetTimeZoneName Time.getZoneName)

    SetTimeZoneName zonename ->
      ({ state | timezonename =
      case zonename of
        Time.Name name -> name
        Time.Offset offset -> "GMT" ++ String.fromFloat (toFloat offset / 60.0)
      }, Task.perform SetTimeNow Time.now)

    SetTimeNow now ->
      ({ state | datetime = (dateTimeFormatted state.timezone now), datetime_valid = True}, Cmd.none)

    UpdateDateTime new_datetime ->
      ({state | datetime = new_datetime, datetime_valid = validateDateTime new_datetime}, Cmd.none)

    UpdateTimeZone tzname ->
      let
          _ = Debug.log "updatetimezone" tzname
      in
          ({state | timezonename = tzname}, Cmd.none)

selectedBirdSorter : Bird -> Bird -> Order
selectedBirdSorter a b =
  if a.selected == b.selected then EQ
  else if a.selected then LT
  else GT

dateTimeFormatted : Time.Zone -> Time.Posix -> String
dateTimeFormatted tz t =
  String.fromInt (Time.toYear tz t)
  ++ "-" ++ (
    case (Time.toMonth tz t) of
      Time.Jan -> "01"
      Time.Feb -> "02"
      Time.Mar -> "03"
      Time.Apr -> "04"
      Time.May -> "05"
      Time.Jun -> "06"
      Time.Jul -> "07"
      Time.Aug -> "08"
      Time.Sep -> "09"
      Time.Oct -> "10"
      Time.Nov -> "11"
      Time.Dec -> "12"
      )
  ++ "-" ++ String.fromInt (Time.toDay tz t)
  ++ "T"
  ++ (if (Time.toHour tz t) < 10 then "0" else "") ++ String.fromInt (Time.toHour tz t)
  ++ ":"
  ++ (if (Time.toMinute tz t) < 10 then "0" else "") ++ String.fromInt (Time.toMinute tz t)

validateDateTime : String -> Bool
validateDateTime s = True -- TODO

getAvailableBirds : String -> Cmd Msg
getAvailableBirds file =
  Http.get
    { url = (UrlB.relative [ file ] [])
    , expect = Http.expectJson ReceiveBirds (JsonD.list JsonD.string)
    }

getAvailableTimeZones : String -> Cmd Msg
getAvailableTimeZones file =
  Http.get
    { url = (UrlB.relative [ file ] [])
    , expect = Http.expectJson ReceiveTimeZones (JsonD.list JsonD.string)
    }

queryPasses : State -> Cmd Msg
queryPasses state =
  Http.get
    { url = state.query_string
    , expect = Http.expectJson ReceivePasses passesDecoder
    }

azimuthDecoder : JsonD.Decoder PassAzimuth
azimuthDecoder =
  JsonD.map3 PassAzimuth
    (JsonD.at ["aos"] JsonD.float)
    (JsonD.at ["tca"] JsonD.float)
    (JsonD.at ["los"] JsonD.float)

timeDecoder : JsonD.Decoder PassTime
timeDecoder =
  JsonD.map3 PassTime
    (JsonD.at ["aos"] JsonD.int)
    (JsonD.at ["tca"] JsonD.int)
    (JsonD.at ["los"] JsonD.int)

passesDecoder : JsonD.Decoder (List Pass)
passesDecoder =
  JsonD.list (JsonD.map6 Pass
    (JsonD.at ["grid"] JsonD.string)
    (JsonD.at ["lat"] JsonD.float)
    (JsonD.at ["lng"] JsonD.float)
    (JsonD.at ["bird"] JsonD.string)
    (JsonD.at ["azimuth"] azimuthDecoder)
    (JsonD.at ["time"] timeDecoder)
    )

targetSelectedValue : JsonD.Decoder String
targetSelectedValue = (JsonD.field "target" JsonD.string)

buildQueryString : State -> String
buildQueryString state =
  UrlB.relative [ "query" ]
  (
  [ UrlB.string "lat" state.lattxt
  , UrlB.string "lng" state.lngtxt
  , UrlB.int "alt" state.min_alt
  , UrlB.string "tzname" state.timezonename
  , UrlB.string "window_start" state.datetime
  ] ++ (List.map (\b -> (UrlB.string "bird" b.name)) (List.filter (\b -> b.selected) state.birds))
  )
